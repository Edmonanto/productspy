"""Google Trends summary shown on every pick card in the winners list."""
from app.routers.winners import _search_summary


def test_summary_keeps_last_26_points_and_status():
    t = {"status": "rising", "growth": 1.5, "term": "ski guards", "geo": "US", "at": "2026-10-30",
         "series": [{"date": f"2026-{i:03d}", "value": i} for i in range(52)]}
    s = _search_summary(t)
    assert s["status"] == "rising" and s["growth"] == 1.5 and s["term"] == "ski guards"
    assert s["series"] == list(range(26, 52))


def test_summary_none_without_data():
    assert _search_summary(None) is None
    assert _search_summary({}) is None
    assert _search_summary({"series": []}) is None


def test_summary_skips_bad_points():
    s = _search_summary({"status": "stable", "series": [{"value": 3}, {"value": None}, "x", {"value": 7}]})
    assert s["series"] == [3, 7]
