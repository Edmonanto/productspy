"""Google Trends: parsing, spike vs sustained, caching, scoring impact."""
from datetime import date, datetime, timedelta, timezone

from app.winners import trends
from app.winners.collectors.base import AdRecord
from app.winners.scoring import aggregate, score, trend_status

TODAY = date(2026, 10, 28)
NOW = datetime(2026, 10, 28, tzinfo=timezone.utc)


def series(vals):
    start = date(2025, 11, 2)
    return [{"date": (start + timedelta(weeks=i)).isoformat(), "value": v} for i, v in enumerate(vals)]


def test_parse_apify_item_drops_partial_week():
    item = {"searchTerm": "posture corrector", "interestOverTime_timelineData": [
        {"time": "1673136000", "value": [40]}, {"time": "1673740800", "value": [55]},
        {"time": "1674345600", "value": [60], "isPartial": True}]}
    pts = trends.series_from_item(item)
    assert [p["value"] for p in pts] == [40, 55]


def test_rising_falling_spike_low():
    assert trends.analyze(series([20] * 40 + [20] * 8 + [40, 45, 50, 55]))["status"] == "rising"
    assert trends.analyze(series([60] * 40 + [60] * 8 + [20, 22, 18, 25]))["status"] == "falling"
    spike = trends.analyze(series([5] * 46 + [8, 15, 100, 70, 40, 30]))
    assert spike["status"] == "spike" and spike["peak_weeks_ago"] <= 6
    assert trends.analyze(series([1, 0, 2] * 17 + [1]))["status"] == "low"
    assert trends.analyze(series([0] * 52))["status"] == "no_data"
    assert trends.analyze(series([30] * 52))["status"] == "stable"


def test_cache_ttl():
    assert trends.needs_refresh(None, TODAY)
    assert not trends.needs_refresh({"at": "2026-10-25"}, TODAY)
    assert trends.needs_refresh({"at": "2026-10-01"}, TODAY)
    assert trends.geo_for("UK") == "GB" and trends.geo_for("FR") == "FR"


async def test_step_fetches_only_stale_and_maps_terms(monkeypatch):
    prods = {
        "a": ({"title": "Posture Corrector", "attributes": {}}, []),
        "b": ({"title": "LED Projector", "attributes": {"trends": {"US": {"at": "2026-10-27", "status": "stable"}}}}, []),
    }
    saved = []

    async def fetch(terms, market):
        assert terms == ["posture corrector"]
        return {"posture corrector": series([20] * 48 + [40, 45, 50, 55])}

    async def save(pid, market, data):
        saved.append((pid, data["status"]))
    monkeypatch.setattr(trends, "trends_on", lambda: True)
    monkeypatch.setattr(trends, "llm_available", lambda: False)
    monkeypatch.setattr(trends, "fetch", fetch)
    monkeypatch.setattr(trends, "save", save)
    stats: dict = {}
    got = await trends.trends_step("US", ["a", "b"], prods, TODAY, stats)
    assert saved == [("a", "rising")] and set(got) == {"a", "b"}
    assert stats == {"trends_cached": 1, "trends_fetched": 1}


def _ads():
    return [AdRecord(platform="meta", external_id=f"m{i}", market="US", advertiser_id=f"s{i}",
                     started_at=NOW - timedelta(days=40)) for i in range(4)]


def test_search_signal_moves_demand_and_trend():
    base = score(aggregate(_ads(), now=NOW, sell_price_usd=30, cost_usd=6))
    rising = score(aggregate(_ads(), now=NOW, sell_price_usd=30, cost_usd=6, search_status="rising",
                             search_growth=1.6, search_level=40, search_term="posture corrector", search_geo="US"))
    falling = score(aggregate(_ads(), now=NOW, sell_price_usd=30, cost_usd=6, search_status="falling",
                              search_growth=0.5, search_level=10, search_term="x", search_geo="US"))
    assert rising.breakdown["demand"] > falling.breakdown["demand"]
    assert rising.signals["trend"] == "growing" and "60%" in rising.signals["trend_why"]
    texts = " ".join(e["text"] for e in rising.signals["criteria"]["demand"]["evidence"])
    assert "Google searches rising in US" in texts and "not sales" in texts
    assert base.signals["trend"] in ("stable", "unknown")


def test_spike_is_its_own_trend_and_lowers_sustainability():
    sig = aggregate(_ads(), now=NOW, search_status="spike", search_growth=4.0, search_level=60, search_term="x")
    assert trend_status(sig)[0] == "spike"
    res = score(sig)
    assert any("spike" in e["text"] for e in res.signals["criteria"]["risk"]["evidence"])


async def test_async_actor_run_polls_until_done(monkeypatch):
    import httpx
    from app import config
    from app.winners.collectors import apify
    calls = []

    class R:
        def __init__(self, code, data):
            self.status_code, self._d, self.text = code, data, ""

        def json(self):
            return self._d

    class Client:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

        async def post(self, url, **k):
            calls.append(("post", url))
            assert "Bearer tok" in k["headers"]["Authorization"] and "token" not in (k.get("params") or {})
            return R(201, {"data": {"id": "run1", "status": "RUNNING"}})

        async def get(self, url, **k):
            calls.append(("get", url))
            if url.endswith("/actor-runs/run1"):
                n = sum(1 for c in calls if c[1].endswith("run1"))
                return R(200, {"data": {"id": "run1", "status": "SUCCEEDED" if n >= 2 else "RUNNING",
                                        "defaultDatasetId": "ds1"}})
            return R(200, [{"searchTerm": "x", "interestOverTime_timelineData": []}])

    monkeypatch.setattr(httpx, "AsyncClient", Client)
    monkeypatch.setattr(config, "APIFY_TOKEN", "tok")
    items = await apify.run_actor_async("apify~google-trends-scraper", {"searchTerms": ["x"]})
    assert items == [{"searchTerm": "x", "interestOverTime_timelineData": []}]
    assert calls[-1][1].endswith("/datasets/ds1/items")


async def test_apify_hard_limit_is_reported_clearly(monkeypatch):
    import httpx
    import pytest
    from app import config
    from app.winners.collectors import apify

    class R:
        status_code = 403
        text = '{"error":{"type":"platform-feature-disabled","message":"Monthly usage hard limit exceeded"}}'

    class Client:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, *a, **k): return R()

    monkeypatch.setattr(httpx, "AsyncClient", Client)
    monkeypatch.setattr(config, "APIFY_TOKEN", "tok")
    monkeypatch.setattr(apify, "_blocked", None)
    with pytest.raises(apify.ApifyLimitError, match="monthly usage hard limit"):
        await apify.run_actor("curious_coder~facebook-ads-library-scraper", {})
    with pytest.raises(apify.ApifyLimitError):            # later calls fail fast, no request
        await apify.run_actor_async("apify~google-trends-scraper", {})
    monkeypatch.setattr(apify, "_blocked", None)


async def test_meta_budget_is_split_across_urls(monkeypatch):
    from app import config
    from app.winners.collectors import apify
    from app.winners.markets import get_market
    sent = {}

    async def fake_run(actor, payload, timeout=600):
        sent.update(payload)
        return []
    monkeypatch.setattr(apify, "run_actor", fake_run)
    monkeypatch.setattr(config, "APIFY_META_MAX", 150)
    await apify.ApifyMetaCollector().collect(get_market("US"))
    assert len(sent["urls"]) * sent["count"] <= 160          # ~150 ads per market, not 300 per url


async def test_paid_sources_skipped_when_scraped_recently(monkeypatch):
    from app.winners import pipeline, store

    class Paid:
        name, paid = "apify_meta", True
        calls = 0

        async def collect(self, market):
            Paid.calls += 1
            return []

    async def recent(m):
        return 3.0

    async def noop(*a, **k):
        return 1 if a and a[0] == "US" else None

    monkeypatch.setattr(store, "hours_since_collected", recent)
    monkeypatch.setattr(store, "start_run", noop)
    monkeypatch.setattr(store, "finish_run", noop)

    async def skip(*a, **k):
        return None
    for fn in ("extract_step", "enrich_step", "score_step"):
        monkeypatch.setattr(pipeline, fn, skip)
    res = await pipeline.run_market("US", collectors=[Paid()])
    assert Paid.calls == 0 and "already scraped" in res["stats"]["collect_skipped"]
    res = await pipeline.run_market("US", collectors=[Paid()], collect="always")
    assert Paid.calls == 1
    res = await pipeline.run_market("US", collectors=[Paid()], collect="never")
    assert Paid.calls == 1 and "no scraping" in res["stats"]["collect_skipped"]
