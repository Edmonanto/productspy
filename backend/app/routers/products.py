"""/products — trending, search, detail, rescore."""
from fastapi import APIRouter, Depends, HTTPException, Query, status

from .. import quota, repository, scoring
from ..auth import CurrentUser, current_user
from ..schemas import Product, ProductList, RescoreResponse

router = APIRouter(prefix="/products", tags=["products"])


@router.get("/trending", response_model=ProductList)
async def get_trending(
    source: str = Query("", description="aliexpress | amazon | tiktok | all"),
    category: str = Query(""),
    min_score: int = Query(0, ge=0, le=100),
    limit: int = Query(40, ge=1, le=100),
    user: CurrentUser = Depends(current_user),
) -> ProductList:
    """Browsing trending products does not consume search quota."""
    products, total = await repository.trending(source, category, min_score, limit)
    return ProductList(products=products, total=total)


@router.get("/search", response_model=ProductList)
async def search_products(
    q: str = Query(..., min_length=1),
    min_score: int = Query(40, ge=0, le=100),
    limit: int = Query(40, ge=1, le=100),
    user: CurrentUser = Depends(current_user),
) -> ProductList:
    subscription, _ = await repository.subscription(user.id)
    await quota.consume_search(user.id, subscription.plan)

    products, total = await repository.search(q, min_score, limit)
    return ProductList(products=products, total=total)


@router.get("/{product_id}", response_model=Product)
async def get_product(
    product_id: str, user: CurrentUser = Depends(current_user)
) -> Product:
    product = await repository.get_product(product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


@router.post("/{product_id}/rescore", response_model=RescoreResponse)
async def rescore_product(
    product_id: str, user: CurrentUser = Depends(current_user)
) -> RescoreResponse:
    product = await repository.get_product(product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Product not found")

    score = scoring.rescore(product)
    await repository.save_score(product_id, score)
    return RescoreResponse(score=score)
