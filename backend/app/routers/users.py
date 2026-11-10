"""/users — the current user's profile, subscription and free trial."""
from fastapi import APIRouter, BackgroundTasks, Depends

from .. import funnel, owner_notify, repository, trial
from ..auth import CurrentUser, current_user
from ..schemas import Me, Trial

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=Me)
async def get_me(background: BackgroundTasks, user: CurrentUser = Depends(current_user)) -> Me:
    # The dashboard calls this on every page load, so a brand-new account's
    # free trial starts here (no-op for existing accounts).
    if await repository.ensure_subscription(user.id, user.email):
        await funnel.record("account_created", user_id=user.id, lang=user.locale)
        background.add_task(owner_notify.notify_signup, user.email, user.name, user.locale)
    subscription, _ = await repository.subscription(user.id)
    row = await repository.subscription_row(user.id)
    return Me(
        id=user.id,
        email=user.email,
        name=user.name,
        avatar_url=user.avatar_url,
        subscription=subscription,
        trial=Trial(**trial.trial_info(row)),
    )
