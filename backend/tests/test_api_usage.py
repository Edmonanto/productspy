"""Metered 1688 calls: daily caps, out-of-credits handling, usage accounting,
and the /status report built from it.

HTTP goes through httpx.MockTransport, so no real (paid) call is ever made.
"""
import json
import pathlib
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app import config, repository
from app.providers import metering
from app.providers import aggregator1688
from app.providers.aggregator1688 import Aggregator1688Provider, _balance, _error_message
from app.providers.base import ApiCall
from app.routers.status import build_status

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
SEARCH = json.loads((FIXTURES / "search_1688.json").read_text())
OUT_OF_CREDITS = {"code": "error", "msg": "token次数不足"}
NOW = datetime.now(timezone.utc)


@pytest.fixture(autouse=True)
def settings(monkeypatch):
    monkeypatch.setattr(config, "CNY_PER_USD", 7.15)
    monkeypatch.setattr(config, "WHOLESALE_MARKUP", 3.0)
    monkeypatch.setattr(config, "AGG1688_INCLUDE_ADS", True)
    monkeypatch.setattr(config, "AGG1688_ENRICH_TOP", 0)
    monkeypatch.setattr(config, "AGG1688_DAILY_SEARCH_CALLS", 10)
    monkeypatch.setattr(config, "AGG1688_DAILY_DETAIL_CALLS", 10)
    monkeypatch.setattr(config, "AGG1688_LOW_BALANCE", 20)


def serve(monkeypatch, responses):
    """Answer successive requests with `responses`; return the request log."""
    seen: list[httpx.Request] = []
    queue = list(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=queue.pop(0))

    real = httpx.AsyncClient
    monkeypatch.setattr(
        aggregator1688.httpx, "AsyncClient",
        lambda **kw: real(transport=httpx.MockTransport(handler), **kw),
    )
    return seen


def provider(keywords):
    return Aggregator1688Provider(
        search_url="http://x/search", search_token="t",
        detail_url="http://y/detail", detail_token="t2", keywords=keywords,
    )


# ── provider ────────────────────────────────────────────────────────────────
async def test_keeps_every_offer_a_call_returns(monkeypatch):
    serve(monkeypatch, [SEARCH])
    p = provider(["衣服"])
    parseable = len(p.parse_search(SEARCH))
    assert parseable > 1
    # limit=1 used to truncate each keyword's results; a paid call's data is kept.
    assert len(await p.fetch(limit=1)) == parseable


async def test_out_of_credits_stops_remaining_keywords(monkeypatch):
    seen = serve(monkeypatch, [SEARCH, OUT_OF_CREDITS, SEARCH])
    p = provider(["a", "b", "c"])
    products = await p.fetch()

    assert len(seen) == 2                    # "c" was never requested
    assert products                          # "a"'s results survive
    assert p.out_of_credits == {"search"}
    assert p.call_log[-1].out_of_credits and p.call_log[-1].balance == 0


async def test_daily_budget_skips_calls(monkeypatch):
    seen = serve(monkeypatch, [SEARCH, SEARCH])
    p = provider(["a", "b", "c"])
    p.remaining["search"] = 1
    await p.fetch()
    assert len(seen) == 1
    assert len(p.call_log) == 1              # skipped calls aren't logged as calls


async def test_generic_error_is_a_failure_not_out_of_credits(monkeypatch):
    serve(monkeypatch, [{"code": "error", "msg": "keyword invalid"}, SEARCH])
    p = provider(["a", "b"])
    products = await p.fetch()
    assert products and not p.out_of_credits
    assert [c.ok for c in p.call_log] == [False, True]


@pytest.mark.parametrize("body,expected", [
    ({"code": "success"}, None),
    ({"ret": "SUCCESS::调用成功"}, None),
    ({"code": "error", "msg": "token次数不足"}, "token次数不足"),
    ({"ret": "FAIL_SYS::系统错误"}, "FAIL_SYS::系统错误"),
    ([], "non-object response"),
])
def test_error_message(body, expected):
    assert _error_message(body) == expected


def test_balance_reads_either_key():
    assert _balance({"left_num": 99}) == 99
    assert _balance({"left_nums": "12"}) == 12
    assert _balance({}) is None


# ── worker accounting ───────────────────────────────────────────────────────
async def test_budget_is_lowered_by_todays_usage(monkeypatch):
    async def used(_name):
        return {"search": 7}

    monkeypatch.setattr(repository, "api_calls_today", used)
    p = provider(["a"])
    await metering.apply_budget(p)
    assert p.remaining == {"search": 3, "detail": 10}


async def test_budget_never_goes_negative(monkeypatch):
    async def used(_name):
        return {"search": 50}

    monkeypatch.setattr(repository, "api_calls_today", used)
    p = provider(["a"])
    await metering.apply_budget(p)
    assert p.remaining["search"] == 0


async def test_unmetered_providers_are_untouched():
    class Plain:
        name = "plain"

    await metering.apply_budget(Plain())  # no daily_budgets: no DB call, no error


async def test_usage_failure_does_not_fail_the_run(monkeypatch):
    async def broken(*_a):
        raise RuntimeError("db down")

    monkeypatch.setattr(repository, "record_api_calls", broken)
    p = provider(["a"])
    p.call_log = [ApiCall("search", ok=True)]
    await metering.record_usage(p)  # logs, doesn't raise


# ── /status ─────────────────────────────────────────────────────────────────
def _raw(run_error=None, upserted=50, balance=80, out_at=None):
    return {
        "runs": [{
            "provider": "1688-aggregator", "started_at": NOW, "finished_at": NOW,
            "fetched": upserted, "upserted": upserted, "error": run_error,
            "last_success_at": NOW - timedelta(days=1),
        }],
        "usage": [{
            "provider": "1688-aggregator", "endpoint": "search", "usage_day": NOW.date(),
            "last_balance": balance, "last_error": None, "out_of_credits_at": out_at,
            "calls_today": 3,
        }],
        "products": {"1688": 180},
    }


CAPS = {"1688-aggregator": {"search": 10, "detail": 10}}


@pytest.mark.parametrize("kwargs,state", [
    ({}, "ok"),
    ({"balance": 5}, "low_credits"),
    ({"out_at": NOW, "balance": 0}, "out_of_credits"),
    ({"run_error": "boom"}, "failing"),
    ({"upserted": 0}, "failing"),
])
def test_status_states(kwargs, state):
    status = build_status(_raw(**kwargs), CAPS, is_admin=True)
    assert status.sources[0].state == state


def test_status_hides_operator_detail_from_customers():
    status = build_status(_raw(run_error="token次数不足"), CAPS, is_admin=False)
    source = status.sources[0]
    assert source.last_error is None and source.endpoints == []
    assert source.state == "failing"          # customers still learn data is stale
    assert status.products == {"1688": 180}


def test_status_shows_usage_to_admins():
    status = build_status(_raw(), CAPS, is_admin=True)
    search = status.sources[0].endpoints[0]
    assert (search.calls_today, search.daily_cap, search.balance) == (3, 10, 80)
    assert status.last_updated_at == NOW - timedelta(days=1)


def test_status_lists_configured_provider_that_never_ran():
    status = build_status({"runs": [], "usage": [], "products": {}}, CAPS, is_admin=True)
    assert status.sources[0].state == "never_run"
    assert status.last_updated_at is None


# ── English search (lives here to keep the repository unit tests together) ──
from app.repository import search_patterns  # noqa: E402


def test_search_patterns_one_per_word():
    assert search_patterns("  Pet  Water fountain ") == ["%pet%", "%water%", "%fountain%"]
    assert search_patterns("") == []


def test_search_patterns_escape_wildcards():
    # A user typing % or _ must not turn the query into a match-everything.
    assert search_patterns("100% cotton_shirt") == ["%100\%%", "%cotton\_shirt%"]


def test_status_score_distribution_fills_empty_buckets():
    raw = {"runs": [], "usage": [], "products": {}, "score_buckets": {2: 5, 4: 1}}
    status = build_status(raw, {}, is_admin=False)
    assert [(b.range, b.count) for b in status.score_distribution] == [
        ("0–19", 0), ("20–39", 0), ("40–59", 5), ("60–79", 0), ("80–100", 1),
    ]
