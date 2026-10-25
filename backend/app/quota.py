"""Per-plan limits shared by the routers.

Daily Winners limits (markets, picks per day, history, evidence, CSV) live in
config.WINNERS_PLANS and are enforced in routers/winners.py.
"""
from fastapi import HTTPException, status

from . import config, repository


def watchlist_limit(plan: str) -> int | str:
    return config.PLAN_WATCHLIST_LIMITS.get(plan, config.PLAN_WATCHLIST_LIMITS[config.DEFAULT_PLAN])


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
