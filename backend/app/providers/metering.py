"""Daily budgets and usage accounting for metered (prepaid) providers.

Shared by the ingestion worker and request-time detail fetches, so both draw
from the same per-day caps in api_usage. Providers that aren't metered have
no `daily_budgets` and pass through untouched.
"""
import logging

from .. import repository

log = logging.getLogger(__name__)


async def apply_budget(provider) -> None:
    """Lower a provider's per-endpoint allowance by today's recorded usage."""
    budgets = getattr(provider, "daily_budgets", None)
    if not budgets:
        return
    used = await repository.api_calls_today(provider.name)
    provider.remaining = {ep: max(0, cap - used.get(ep, 0)) for ep, cap in budgets.items()}
    log.info("%s: calls left today %s (caps %s)", provider.name, provider.remaining, budgets)


async def record_usage(provider) -> None:
    """Persist the provider's call log, then clear it so it isn't counted twice."""
    calls = getattr(provider, "call_log", None)
    if not calls:
        return
    try:
        await repository.record_api_calls(provider.name, calls)
        provider.call_log = []
    except Exception:
        # Accounting must not turn a good run or page view into a failure.
        log.exception("%s: could not record API usage", provider.name)
