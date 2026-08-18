"""Per-plan quota helpers shared by the routers."""
from fastapi import HTTPException, status

from . import config, repository
from .schemas import Quota


def search_limit(plan: str) -> int | str:
    return config.PLAN_SEARCH_LIMITS.get(plan, config.PLAN_SEARCH_LIMITS[config.DEFAULT_PLAN])


def watchlist_limit(plan: str) -> int | str:
    return config.PLAN_WATCHLIST_LIMITS.get(plan, config.PLAN_WATCHLIST_LIMITS[config.DEFAULT_PLAN])


async def build_quota(user_id: str, plan: str) -> Quota:
    limit = search_limit(plan)
    used = await repository.searches_used_today(user_id)
    remaining: int | str = (
        config.UNLIMITED if limit == config.UNLIMITED else max(0, int(limit) - used)
    )
    return Quota(plan=plan, limit=limit, used=used, remaining=remaining)


async def consume_search(user_id: str, plan: str) -> None:
    """Charge one search against the daily quota, or reject with 429."""
    limit = search_limit(plan)
    if limit == config.UNLIMITED:
        return

    used = await repository.searches_used_today(user_id)
    if used >= int(limit):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Daily search limit reached ({limit} on the {plan} plan). "
                "Upgrade for more searches."
            ),
        )
    await repository.increment_search(user_id)


async def enforce_watchlist_limit(user_id: str, plan: str) -> None:
    limit = watchlist_limit(plan)
    if limit == config.UNLIMITED:
        return

    count = await repository.watchlist_count(user_id)
    if count >= int(limit):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Watchlist limit reached ({limit} on the {plan} plan). "
                "Upgrade to save more products."
            ),
        )
