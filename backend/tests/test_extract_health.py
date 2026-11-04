"""A starved extract step must not report a clean night."""
from app import alerts
from app.winners.pipeline import extract_health


def test_no_ai_key_with_unidentified_ads_is_an_error():
    stats, errors = {"unidentified_ads": 17, "linked_ads": 0}, []
    extract_health(stats, errors, ai=False)
    assert stats["ai_extract"] == "off"
    assert len(errors) == 1 and "No AI key" in errors[0]["error"] and "17" in errors[0]["error"]


def test_ai_on_but_nothing_linked_is_an_error():
    errors = []
    extract_health({"unidentified_ads": 9, "linked_ads": 0}, errors, ai=True)
    assert errors and "named none of the 9" in errors[0]["error"]


def test_healthy_nights_add_nothing():
    for stats, ai in (({"unidentified_ads": 0, "linked_ads": 0}, False),
                      ({"unidentified_ads": 3, "linked_ads": 40}, True),
                      ({}, True)):
        errors = []
        extract_health(dict(stats), errors, ai)
        assert errors == []


def test_alert_when_nothing_reaches_55():
    res = [{"market": "US", "status": "ok", "errors": [],
            "stats": {"winners": 0, "rising": 0, "watch": 5, "top_score": 54}}]
    problems = alerts.scan_problems(res, min_picks=5)
    assert problems == ["US: no product scored 55+ today (best 54) — the picks are weak signals only; "
                        "usually missing Facebook/TikTok ad data"]
    ok = [{"market": "US", "status": "ok", "errors": [], "stats": {"winners": 3, "rising": 2, "watch": 1}}]
    assert alerts.scan_problems(ok, min_picks=5) == []


async def test_unlinked_ads_looks_back_14_days_by_default(monkeypatch):
    from app import db
    from app.winners import store
    seen = {}

    async def fetch(sql, *args):
        seen["sql"], seen["args"] = sql, args
        return []

    monkeypatch.setattr(db, "fetch", fetch)
    await store.unlinked_ads("US")
    assert seen["args"] == ("US", 600, 14) and "make_interval(days => $3)" in seen["sql"]
    await store.unlinked_ads("US", days=3)
    assert seen["args"][2] == 3
