"""Smoke tests: routing, auth, response shapes, quota and scoring.

The database layer is stubbed, so these run without Postgres.
"""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app import db, quota, repository, scoring
from app.auth import CurrentUser, current_user
from app.main import app
from app.schemas import AdSignal, Product, Score, Subscription

USER = CurrentUser(id="11111111-1111-1111-1111-111111111111", email="e@x.com",
                   name="Edmond", avatar_url=None)

PRODUCT = Product(
    id="22222222-2222-2222-2222-222222222222",
    title="LED Dog Collar",
    image_url=None,
    product_url="https://example.com/p/1",
    category="pets",
    price_usd=24.99,
    cost_usd=4.20,
    source="aliexpress",
    score=Score(overall_score=80, demand_score=90, margin_score=70,
                competition_score=60, trend_score=85, ai_summary="strong"),
    suppliers=[],
    ad_signals=[AdSignal(platform="tiktok", ad_count=50,
                         last_seen_at=datetime.now(timezone.utc))],
)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(db, "connect", lambda: _noop())
    monkeypatch.setattr(db, "disconnect", lambda: _noop())
    app.dependency_overrides[current_user] = lambda: USER
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


async def _noop():
    return None


def _free_plan(*_args, **_kwargs):
    async def inner(*a, **k):
        return Subscription(plan="free", status="active", current_period_end=None), "none"
    return inner()


# ── Auth ────────────────────────────────────────────────────────────────────
def test_protected_route_rejects_missing_token(monkeypatch):
    """Without the dependency override, a tokenless call must 401."""
    monkeypatch.setattr(db, "connect", lambda: _noop())
    monkeypatch.setattr(db, "disconnect", lambda: _noop())
    with TestClient(app) as c:
        assert c.get("/api/v1/users/me").status_code == 401


def test_health(monkeypatch):
    monkeypatch.setattr(db, "connect", lambda: _noop())
    monkeypatch.setattr(db, "disconnect", lambda: _noop())

    async def healthy():
        return True

    monkeypatch.setattr(db, "healthy", healthy)
    with TestClient(app) as c:
        assert c.get("/health").json() == {"ok": True, "database": True}


# ── users/me ────────────────────────────────────────────────────────────────
def test_me_shape(client, monkeypatch):
    monkeypatch.setattr(repository, "subscription", lambda uid: _free_plan())

    async def used(_uid):
        return 2

    monkeypatch.setattr(repository, "searches_used_today", used)

    body = client.get("/api/v1/users/me").json()
    assert body["id"] == USER.id
    assert body["subscription"] == {"plan": "free", "status": "active",
                                    "current_period_end": None}
    # free plan = 5 searches/day, 2 used
    assert body["quota"] == {"plan": "free", "limit": 5, "used": 2, "remaining": 3}


# ── products ────────────────────────────────────────────────────────────────
def test_trending_shape(client, monkeypatch):
    async def trending(*a, **k):
        return [PRODUCT], 1

    monkeypatch.setattr(repository, "trending", trending)

    body = client.get("/api/v1/products/trending?source=all&min_score=50&limit=40").json()
    assert body["total"] == 1
    p = body["products"][0]
    # Field names the frontend's Product interface requires
    assert set(p) >= {"id", "title", "image_url", "product_url", "category",
                      "price_usd", "cost_usd", "source", "score", "suppliers",
                      "ad_signals"}
    assert p["score"]["overall_score"] == 80


def test_search_consumes_quota(client, monkeypatch):
    monkeypatch.setattr(repository, "subscription", lambda uid: _free_plan())
    calls = {"inc": 0}

    async def used(_uid):
        return 0

    async def inc(_uid):
        calls["inc"] += 1
        return 1

    async def search(*a, **k):
        return [PRODUCT], 1

    monkeypatch.setattr(repository, "searches_used_today", used)
    monkeypatch.setattr(repository, "increment_search", inc)
    monkeypatch.setattr(repository, "search", search)

    assert client.get("/api/v1/products/search?q=collar").status_code == 200
    assert calls["inc"] == 1


def test_search_blocked_when_quota_exhausted(client, monkeypatch):
    monkeypatch.setattr(repository, "subscription", lambda uid: _free_plan())

    async def used(_uid):
        return 5  # free limit reached

    monkeypatch.setattr(repository, "searches_used_today", used)

    res = client.get("/api/v1/products/search?q=collar")
    assert res.status_code == 429
    assert "limit" in res.json()["detail"].lower()


def test_product_404(client, monkeypatch):
    async def get_product(_pid):
        return None

    monkeypatch.setattr(repository, "get_product", get_product)
    assert client.get("/api/v1/products/nope").status_code == 404


def test_rescore_persists(client, monkeypatch):
    saved = {}

    async def get_product(_pid):
        return PRODUCT

    async def save_score(pid, score):
        saved["pid"], saved["score"] = pid, score

    monkeypatch.setattr(repository, "get_product", get_product)
    monkeypatch.setattr(repository, "save_score", save_score)

    body = client.post(f"/api/v1/products/{PRODUCT.id}/rescore").json()
    assert "score" in body
    assert saved["pid"] == PRODUCT.id
    # margin = (24.99-4.20)/24.99 = 83% -> saturates at 100
    assert body["score"]["margin_score"] == 100


# ── watchlist ───────────────────────────────────────────────────────────────
def test_watchlist_free_plan_limit(client, monkeypatch):
    async def get_product(_pid):
        return PRODUCT

    async def count(_uid):
        return 10  # free plan cap

    monkeypatch.setattr(repository, "get_product", get_product)
    monkeypatch.setattr(repository, "subscription", lambda uid: _free_plan())
    monkeypatch.setattr(repository, "watchlist_count", count)

    res = client.post(f"/api/v1/watchlist/{PRODUCT.id}")
    assert res.status_code == 403


# ── billing ─────────────────────────────────────────────────────────────────
def test_billing_status(client, monkeypatch):
    monkeypatch.setattr(repository, "subscription", lambda uid: _free_plan())
    body = client.get("/api/v1/billing/status").json()
    assert body["plan"] == "free"
    assert body["search_quota"] == 5
    assert body["can_manage"] is False


def test_billing_checkout_not_implemented(client):
    res = client.post("/api/v1/billing/checkout?plan=pro&provider=stripe")
    assert res.status_code == 501
    assert "detail" in res.json()  # frontend surfaces error.detail


# ── scoring (pure) ──────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "price,cost,expected",
    [(100.0, 30.0, 100), (100.0, 65.0, 50), (100.0, 100.0, 0), (None, 5.0, 0), (0.0, 0.0, 0)],
)
def test_margin_score(price, cost, expected):
    assert scoring.margin_score(price, cost) == expected


def test_competition_score_inverts_ad_volume():
    now = datetime.now(timezone.utc)
    few = [AdSignal(platform="tiktok", ad_count=10, last_seen_at=now)]
    many = [AdSignal(platform="tiktok", ad_count=400, last_seen_at=now)]
    assert scoring.competition_score(few) > scoring.competition_score(many)
    assert scoring.competition_score([]) == 50  # unknown -> neutral


def test_overall_weights_sum_to_one():
    assert abs(sum(scoring.WEIGHTS.values()) - 1.0) < 1e-9
