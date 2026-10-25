"""/winners routes: plan gating, market limits, shapes. Database stubbed."""
import json
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import db, repository
from app.auth import CurrentUser, current_user
from app.main import app
from app.schemas import Subscription
from app.winners import store

USER = CurrentUser(id="11111111-1111-1111-1111-111111111111", email="e@x.com",
                   name="Edmond", avatar_url=None)
PID = "33333333-3333-3333-3333-333333333333"
TODAY = datetime.now(timezone.utc).date()


async def _noop(*_a, **_k):
    return None


def _pick(rank: int, total: int = 80, tier: str = "winner") -> dict:
    return {
        "rank": rank, "tier": tier, "total": total, "product_id": PID, "pick_date": TODAY,
        "breakdown": json.dumps({"scaling": 26, "engagement": 15, "demand": 19, "margin": 15, "freshness": 7}),
        "reasons": json.dumps(["Ad still running after 46 days on Facebook/Instagram"]),
        "penalties": json.dumps([]), "confidence": "high",
        "signals": json.dumps({"max_days_running": 46, "creatives": 33, "advertisers": 11,
                               "meta_ads": 13, "tiktok_ads": 1, "videos": 9, "total_views": 12_000_000}),
        "title": "Posture Corrector", "image_url": None, "category": "health",
        "price_usd": 34.99, "cost_usd": 6.2, "cost_estimated": False,
        "product_url": "https://store.example/products/posture-corrector",
        "attributes": json.dumps({}), "supplier_url": None,
        "ad_url": "https://www.facebook.com/ads/library/?id=1",
        "store_url": "https://store.example/products/posture-corrector",
    }


@pytest.fixture
def make_client(monkeypatch):
    """Client factory for a given effective plan and followed markets."""
    state: dict = {"followed": []}

    def factory(plan: str = "free", followed: list[str] | None = None, picks: int = 10):
        state["followed"] = list(followed or [])

        async def subscription(_uid):
            return Subscription(plan=plan, status="active", current_period_end=None), "none"

        async def followed_markets(_uid):
            return list(state["followed"])

        async def save_followed(_uid, markets):
            state["followed"] = list(markets)

        async def latest_pick_date(_m, _d):
            return TODAY if picks else None

        async def get_picks(_m, _d):
            return [_pick(i + 1, 90 - i) for i in range(picks)]

        monkeypatch.setattr(db, "connect", _noop)
        monkeypatch.setattr(db, "disconnect", _noop)
        monkeypatch.setattr(repository, "subscription", subscription)
        monkeypatch.setattr(store, "followed_markets", followed_markets)
        monkeypatch.setattr(store, "save_followed_markets", save_followed)
        monkeypatch.setattr(store, "latest_pick_date", latest_pick_date)
        monkeypatch.setattr(store, "picks", get_picks)
        app.dependency_overrides[current_user] = lambda: USER
        return TestClient(app)

    yield factory, state
    app.dependency_overrides.clear()


def test_free_sees_three_and_the_rest_is_locked(make_client):
    factory, _ = make_client
    with factory("free") as c:
        body = c.get("/api/v1/winners?market=US").json()
    unlocked = [w for w in body["winners"] if not w["locked"]]
    locked = [w for w in body["winners"] if w["locked"]]
    assert len(unlocked) == 3 and len(locked) == 7 and body["locked_count"] == 7
    # A locked pick leaks nothing but its rank and score.
    assert set(locked[0]) == {"rank", "tier", "total", "locked"}
    top = unlocked[0]
    assert top["stats"]["sources"] == ["facebook_ads", "tiktok_ads", "tiktok_organic"]
    assert top["product"]["margin_pct"] == 82
    assert set(top["breakdown"]) == {"scaling", "engagement", "demand", "margin", "freshness"}


def test_pro_sees_all_ten(make_client):
    factory, _ = make_client
    with factory("pro") as c:
        body = c.get("/api/v1/winners?market=US").json()
    assert len(body["winners"]) == 10 and body["locked_count"] == 0


def test_first_market_is_followed_automatically_then_locked(make_client):
    factory, state = make_client
    with factory("free") as c:
        assert c.get("/api/v1/winners?market=FR").status_code == 200
        assert state["followed"] == ["FR"]
        r = c.get("/api/v1/winners?market=US")
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "market_locked"


def test_preferences_respect_plan_limit(make_client, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "WINNERS_MARKETS", "US,UK,FR,AU")
    factory, state = make_client
    with factory("pro") as c:
        assert c.post("/api/v1/winners/preferences", json={"markets": ["us", "fr", "UK"]}).status_code == 200
        assert state["followed"] == ["US", "FR", "UK"]
        r = c.post("/api/v1/winners/preferences", json={"markets": ["US", "FR", "UK", "AU"]})
        assert r.status_code == 403
        assert c.post("/api/v1/winners/preferences", json={"markets": ["XX"]}).status_code == 400


def test_history_is_plan_limited(make_client):
    factory, _ = make_client
    old = (TODAY - timedelta(days=10)).isoformat()
    with factory("starter") as c:  # 7 days
        assert c.get(f"/api/v1/winners?market=US&date={old}").status_code == 403
    with factory("pro") as c:      # 30 days
        assert c.get(f"/api/v1/winners?market=US&date={old}").status_code == 200


def test_no_picks_yet(make_client):
    factory, _ = make_client
    with factory("pro", picks=0) as c:
        body = c.get("/api/v1/winners?market=US").json()
    assert body["winners"] == [] and body["date"] is None


def test_csv_export_gated(make_client):
    factory, _ = make_client
    with factory("starter") as c:
        assert c.get("/api/v1/winners/export.csv?market=US").status_code == 403
    with factory("pro") as c:
        r = c.get("/api/v1/winners/export.csv?market=US")
    assert r.status_code == 200
    assert r.text.count("\n") == 11  # header + 10 picks
    assert "Posture Corrector" in r.text


def test_evidence_hidden_on_free(make_client, monkeypatch):
    factory, _ = make_client

    async def product(_pid):
        return {"id": PID, "title": "Posture Corrector", "image_url": None, "category": None,
                "price_usd": 34.99, "cost_usd": 6.2, "cost_estimated": True, "product_url": "",
                "attributes": "{}", "first_seen_at": datetime.now(timezone.utc)}

    async def history(_pid, _m):
        return [{"scored_on": TODAY, "total": 82, "breakdown": "{}", "reasons": "[]",
                 "penalties": "[]", "confidence": "high", "signals": "{}", "excluded": None}]

    async def ads(_pid, _m):
        return [{"platform": "meta", "advertiser_name": "S", "ad_text": "x", "landing_url": None,
                 "landing_domain": None, "thumbnail_url": None, "ad_url": None,
                 "started_at": datetime.now(timezone.utc) - timedelta(days=30, hours=1), "variant_count": 2,
                 "reach": None, "views": None, "likes": None, "comments": None, "shares": None,
                 "ctr": None}]

    async def suppliers(_pid):
        return []

    monkeypatch.setattr(store, "product", product)
    monkeypatch.setattr(store, "score_history", history)
    monkeypatch.setattr(store, "product_ads", ads)
    monkeypatch.setattr(store, "product_suppliers", suppliers)

    with factory("free") as c:
        free = c.get(f"/api/v1/winners/products/{PID}?market=US").json()
    assert free["ad_evidence_locked"] is True and free["ads"] == {} and free["ad_counts"] == {"meta": 1}
    with factory("pro") as c:
        pro = c.get(f"/api/v1/winners/products/{PID}?market=US").json()
        assert c.get("/api/v1/winners/products/not-a-uuid?market=US").status_code == 404
    assert pro["ads"]["meta"][0]["days_running"] == 30
    assert pro["product"]["cost_estimated"] is True and pro["score"]["total"] == 82


def test_markets_endpoint(make_client):
    factory, _ = make_client
    with factory("pro", followed=["AE", "FR"]) as c:
        body = c.get("/api/v1/winners/markets").json()
    # only launched markets (WINNERS_MARKETS) are offered; a followed market
    # that isn't launched is ignored
    assert [m["code"] for m in body["markets"]] == ["US", "UK", "FR"]
    assert body["following"] == ["FR"]
    assert body["entitlements"]["markets"] == 3


def test_unlaunched_market_is_refused(make_client):
    factory, state = make_client
    with factory("pro") as c:
        r = c.get("/api/v1/winners?market=AE")
        assert r.status_code == 400 and "isn't available yet" in r.json()["detail"]
        assert c.post("/api/v1/winners/preferences", json={"markets": ["AE"]}).status_code == 400
