"""/users — the current user's profile, subscription and quota."""
from fastapi import APIRouter, Depends

from .. import quota, repository
from ..auth import CurrentUser, current_user
from ..schemas import Me

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=Me)
async def get_me(user: CurrentUser = Depends(current_user)) -> Me:
    subscription, _ = await repository.subscription(user.id)
    return Me(
        id=user.id,
        email=user.email,
        name=user.name,
        avatar_url=user.avatar_url,
        subscription=subscription,
        quota=await quota.build_quota(user.id, subscription.plan),
    )
