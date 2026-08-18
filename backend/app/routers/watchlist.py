"""/watchlist — list, add, remove."""
from fastapi import APIRouter, Depends, HTTPException, status

from .. import quota, repository
from ..auth import CurrentUser, current_user
from ..schemas import WatchlistItem, WatchlistResponse

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


@router.get("/", response_model=WatchlistResponse)
async def list_watchlist(user: CurrentUser = Depends(current_user)) -> WatchlistResponse:
    rows = await repository.watchlist(user.id)
    return WatchlistResponse(
        items=[
            WatchlistItem(id=watch_id, product=product, added_at=added_at)
            for watch_id, product, added_at in rows
        ]
    )


@router.post("/{product_id}", status_code=status.HTTP_201_CREATED)
async def add_to_watchlist(
    product_id: str, user: CurrentUser = Depends(current_user)
) -> dict[str, str]:
    if await repository.get_product(product_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Product not found")

    subscription, _ = await repository.subscription(user.id)
    await quota.enforce_watchlist_limit(user.id, subscription.plan)

    await repository.watchlist_add(user.id, product_id)
    return {"message": "Added to watchlist"}


@router.delete("/{product_id}")
async def remove_from_watchlist(
    product_id: str, user: CurrentUser = Depends(current_user)
) -> dict[str, str]:
    await repository.watchlist_remove(user.id, product_id)
    return {"message": "Removed from watchlist"}
