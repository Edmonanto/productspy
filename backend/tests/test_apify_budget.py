"""Our own monthly Apify budget (APIFY_MONTHLY_BUDGET_USD)."""
import pytest

from app import config
from app.winners.collectors import apify


@pytest.fixture(autouse=True)
def reset(monkeypatch):
    monkeypatch.setattr(apify, "_blocked", None)
    monkeypatch.setattr(apify, "_usage_cache", None)
    monkeypatch.setattr(config, "APIFY_MONTHLY_BUDGET_USD", 30.0)


def _usage(used):
    async def f():
        return used, "2026-12-12"
    return f


@pytest.mark.asyncio
async def test_under_budget_runs(monkeypatch):
    monkeypatch.setattr(apify, "_monthly_usage", _usage(12.5))
    await apify._check_budget()           # no error
    assert apify._blocked is None


@pytest.mark.asyncio
async def test_over_budget_stops_every_run(monkeypatch):
    monkeypatch.setattr(apify, "_monthly_usage", _usage(30.01))
    with pytest.raises(apify.ApifyLimitError, match=r"\$30\.01 used of \$30"):
        await apify._check_budget()
    with pytest.raises(apify.ApifyLimitError):
        await apify.run_actor("x~y", {})   # blocked for the rest of the run, no HTTP call


@pytest.mark.asyncio
async def test_unknown_usage_or_off_does_not_block(monkeypatch):
    async def unknown():
        return None
    monkeypatch.setattr(apify, "_monthly_usage", unknown)
    await apify._check_budget()
    monkeypatch.setattr(config, "APIFY_MONTHLY_BUDGET_USD", 0.0)
    monkeypatch.setattr(apify, "_monthly_usage", _usage(999))
    await apify._check_budget()
