"""/status — is the product data fresh, and are the paid data tokens alive?

Everyone signed in gets freshness (when each source last updated, and a
coarse state). Emails in ADMIN_EMAILS also get token balances, today's call
counts against the daily caps, and the raw provider errors.
"""
from typing import Any

from fastapi import APIRouter, Depends

from .. import config, repository
from ..auth import CurrentUser, current_user
from ..providers.registry import enabled_providers
from ..schemas import DataStatus, EndpointUsage, SourceStatus

router = APIRouter(prefix="/status", tags=["status"])


def _state(run: dict[str, Any] | None, endpoints: list[EndpointUsage]) -> str:
    if any(e.out_of_credits for e in endpoints):
        return "out_of_credits"
    if run is None:
        return "never_run"
    if run.get("error") or not run.get("upserted"):
        return "failing"
    if any(e.balance is not None and e.balance < config.AGG1688_LOW_BALANCE for e in endpoints):
        return "low_credits"
    return "ok"


def build_status(raw: dict[str, Any], caps: dict[str, dict[str, int]], is_admin: bool) -> DataStatus:
    runs = {r["provider"]: r for r in raw["runs"]}
    usage: dict[str, list[dict[str, Any]]] = {}
    for u in raw["usage"]:
        usage.setdefault(u["provider"], []).append(u)

    sources: list[SourceStatus] = []
    for provider in sorted(set(runs) | set(usage) | set(caps)):
        run = runs.get(provider)
        endpoints = [
            EndpointUsage(
                endpoint=u["endpoint"],
                calls_today=int(u["calls_today"] or 0),
                daily_cap=caps.get(provider, {}).get(u["endpoint"]),
                balance=u["last_balance"],
                out_of_credits=u["out_of_credits_at"] is not None,
                last_error=u["last_error"],
            )
            for u in usage.get(provider, [])
        ]
        sources.append(
            SourceStatus(
                provider=provider,
                state=_state(run, endpoints),
                last_run_at=run["started_at"] if run else None,
                last_success_at=run["last_success_at"] if run else None,
                last_error=(run or {}).get("error") if is_admin else None,
                endpoints=endpoints if is_admin else [],
            )
        )

    successes = [s.last_success_at for s in sources if s.last_success_at]
    return DataStatus(
        sources=sources,
        products=raw["products"],
        last_updated_at=max(successes) if successes else None,
        is_admin=is_admin,
    )


@router.get("/", response_model=DataStatus)
async def get_status(user: CurrentUser = Depends(current_user)) -> DataStatus:
    caps = {
        p.name: p.daily_budgets
        for p in enabled_providers()
        if getattr(p, "daily_budgets", None)
    }
    is_admin = user.email.lower() in config.ADMIN_EMAILS
    return build_status(await repository.data_status(), caps, is_admin)
