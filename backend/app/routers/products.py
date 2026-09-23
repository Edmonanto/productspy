"""/products — trending, live 1688 search, detail, rescore."""
from fastapi import APIRouter, Depends, HTTPException, Query, status

from .. import quota, repository
from ..auth import CurrentUser, current_user
from ..schemas import Product, ProductList, RescoreResponse
from ..services import catalog
from ..sources.ali1688 import Ali1688Error

router = APIRouter(prefix="/products", tags=["products"])

_UPSTREAM_DOWN = "Product search is temporarily unavailable. Please try again shortly."


@router.get("/trending", response_model=ProductList)
async def get_trending(
    source: str = Query("", description="1688 | all"),
    category: str = Query(""),
    min_score: int = Query(0, ge=0, le=100),
    limit: int = Query(40, ge=1, le=100),
    user: CurrentUser = Depends(current_user),
) -> ProductList:
    """Stored products (filled by the ingest worker). Costs no search quota."""
    products, total = await repository.trending(source, category, min_score, limit)
    return ProductList(products=products, total=total)


@router.get("/search", response_model=ProductList)
async def search_products(
    q: str = Query(..., min_length=1, max_length=100, description="1688 works best with Chinese keywords"),
    page: int = Query(1, ge=1, le=50),
    min_score: int = Query(40, ge=0, le=100),
    limit: int = Query(60, ge=1, le=60),
    user: CurrentUser = Depends(current_user),
) -> ProductList:
    """Live 1688 keyword search (cached). One search of quota per call."""
    subscription, _ = await repository.subscription(user.id)
    await quota.ensure_search_available(user.id, subscription.plan)

    try:
        products, _found = await catalog.search(q, page)
    except Ali1688Error:
        # Upstream failure is not the user's fault: don't charge quota.
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=_UPSTREAM_DOWN)

    await repository.increment_search(user.id)
    ranked = [p for p in products if (p.score.overall_score if p.score else 0) >= min_score]
    return ProductList(products=ranked[:limit], total=len(ranked))


@router.get("/{product_id}", response_model=Product)
async def get_product(
    product_id: str, user: CurrentUser = Depends(current_user)
) -> Product:
    """By product uuid, or by 1688 offer id (imported on first request)."""
    product = await catalog.get_product(product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


@router.post("/{product_id}/rescore", response_model=RescoreResponse)
async def rescore_product(
    product_id: str, user: CurrentUser = Depends(current_user)
) -> RescoreResponse:
    product = await catalog.get_product(product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Product not found")

    score = await catalog.rescore(product.id, product.ad_signals)
    if score is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Product not found")
    return RescoreResponse(score=score)
