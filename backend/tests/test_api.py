"""Smoke tests: routing, auth, response shapes, watchlist and billing.

The database layer is stubbed, so these run without Postgres. Daily Winners
routes are covered in test_winners_api.py, the trial in test_trial.py.
"""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app import config, db, repository
from app.auth import CurrentUser, current_user
from app.main import app
from app.schemas import Subscription, WatchedProduct

USER = CurrentUser(id="11111111-1111-1111-1111-111111111111", email="e@x.com",
                   name="Edmond", avatar_url=None)
PRODUCT_ID = "22222222-2222-2222-2222-222222222222"


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


async def _none(*_a, **_k):
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
        assert c.get("/api/v1/winners?market=US").status_code == 401


def test_health(monkeypatch):
    monkeypatch.setattr(db, "connect", lambda: _noop())
    monkeypatch.setattr(db, "disconnect", lambda: _noop())

    async def healthy():
        return True

    monkeypatch.setattr(db, "healthy", healthy)
    with TestClient(app) as c:
        assert c.get("/health").json() == {"ok": True, "database": True}


def test_old_marketplace_routes_are_gone(client):
    """Trending/search/matching were removed with the marketplace engine."""
    for path in ("/api/v1/products/trending", "/api/v1/products/search?q=cat", "/api/v1/matches/"):
        assert client.get(path).status_code == 404


# ── users/me ────────────────────────────────────────────────────────────────
def test_me_shape(client, monkeypatch):
    monkeypatch.setattr(repository, "subscription", lambda uid: _free_plan())
    monkeypatch.setattr(repository, "ensure_subscription", _none)
    monkeypatch.setattr(repository, "subscription_row", _none)

    body = client.get("/api/v1/users/me").json()
    assert body["id"] == USER.id
    assert body["subscription"] == {"plan": "free", "status": "active",
                                    "current_period_end": None}
    assert body["trial"]["eligible"] is True
    assert "quota" not in body  # search quotas went with search


# ── watchlist ───────────────────────────────────────────────────────────────
def test_watchlist_free_plan_limit(client, monkeypatch):
    async def exists(_pid):
        return True

    async def count(_uid):
        return 10  # free plan cap

    monkeypatch.setattr(repository, "product_exists", exists)
    monkeypatch.setattr(repository, "subscription", lambda uid: _free_plan())
    monkeypatch.setattr(repository, "watchlist_count", count)

    res = client.post(f"/api/v1/watchlist/{PRODUCT_ID}")
    assert res.status_code == 403


def test_watchlist_unknown_product_404(client, monkeypatch):
    async def exists(_pid):
        return False

    monkeypatch.setattr(repository, "product_exists", exists)
    assert client.post(f"/api/v1/watchlist/{PRODUCT_ID}").status_code == 404


def test_watchlist_shape(client, monkeypatch):
    async def watchlist(_uid):
        return [("w1", WatchedProduct(id=PRODUCT_ID, title="Posture Corrector", image_url=None,
                                      price_usd=34.99, cost_usd=6.2, score=82, market="US"),
                 datetime.now(timezone.utc))]

    monkeypatch.setattr(repository, "watchlist", watchlist)
    item = client.get("/api/v1/watchlist/").json()["items"][0]
    assert item["product"]["score"] == 82 and item["product"]["market"] == "US"


# ── billing ─────────────────────────────────────────────────────────────────
def test_billing_status(client, monkeypatch):
    monkeypatch.setattr(repository, "subscription", lambda uid: _free_plan())
    monkeypatch.setattr(repository, "subscription_row", _none)
    body = client.get("/api/v1/billing/status").json()
    assert body["plan"] == "free"
    assert body["can_manage"] is False
    assert body["trial"]["eligible"] is True


def test_billing_checkout_fails_cleanly_when_provider_unconfigured(client, monkeypatch):
    """Without STRIPE_SECRET_KEY, checkout must 501 rather than half-succeed."""
    async def subscription_row(_uid):
        return None

    monkeypatch.setattr(repository, "subscription_row", subscription_row)
    monkeypatch.setattr(config, "STRIPE_SECRET_KEY", "")

    res = client.post("/api/v1/billing/checkout?plan=pro&provider=stripe")
    assert res.status_code == 501
    assert "detail" in res.json()  # frontend surfaces error.detail
