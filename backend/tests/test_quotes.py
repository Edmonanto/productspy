"""Quote requests: customers ask for an exact price on a product; admins answer.

No database: repository functions are replaced per test.
"""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app import config, db, repository
from app.auth import CurrentUser, current_user
from app.main import app

NOW = datetime.now(timezone.utc)

USER = CurrentUser(id="11111111-1111-1111-1111-111111111111", email="buyer@x.com",
                   name="Buyer", avatar_url=None)
ADMIN = CurrentUser(id="33333333-3333-3333-3333-333333333333", email="Boss@X.com",
                    name="Boss", avatar_url=None)
PID = "22222222-2222-2222-2222-222222222222"


@pytest.fixture(autouse=True)
def settings(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_EMAILS", {"boss@x.com"})


async def _noop():
    return None


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(db, "connect", lambda: _noop())
    monkeypatch.setattr(db, "disconnect", lambda: _noop())
    app.dependency_overrides[current_user] = lambda: USER
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── quotes ──────────────────────────────────────────────────────────────────
def _quote_row(**kw):
    base = dict(id="44444444-4444-4444-4444-444444444444", user_id=USER.id,
                user_email=USER.email, product_id=PID, product_title="Posture Corrector",
                quantity=200, destination_country="US", target_price_usd=None,
                notes="", status="open", quoted_unit_usd=None,
                quoted_shipping_usd=None, reply="", created_at=NOW, replied_at=None)
    base.update(kw)
    return base


def test_request_quote(client, monkeypatch):
    seen = {}

    async def product_title(_pid):
        return "Posture Corrector"

    async def today(_uid):
        return 0

    async def create(**kw):
        seen.update(kw)
        return _quote_row(quantity=kw["quantity"])

    monkeypatch.setattr(repository, "product_title", product_title)
    monkeypatch.setattr(repository, "quotes_created_today", today)
    monkeypatch.setattr(repository, "create_quote", create)

    res = client.post("/api/v1/quotes/", json={
        "product_id": PID, "quantity": 200, "destination_country": " US ", "notes": " fast ",
    })
    assert res.status_code == 201
    assert res.json()["status"] == "open"
    assert seen["product_title"] == "Posture Corrector"  # copied at request time
    assert seen["destination_country"] == "US" and seen["notes"] == "fast"


@pytest.mark.parametrize("body", [
    {"product_id": PID, "quantity": 0, "destination_country": "US"},
    {"product_id": PID, "quantity": 5, "destination_country": "U"},
])
def test_request_quote_validates(client, body):
    assert client.post("/api/v1/quotes/", json=body).status_code == 422


def test_request_quote_unknown_product(client):
    res = client.post("/api/v1/quotes/", json={
        "product_id": "not-a-uuid", "quantity": 5, "destination_country": "US",
    })
    assert res.status_code == 404


def test_request_quote_daily_limit(client, monkeypatch):
    async def product_title(_pid):
        return "Posture Corrector"

    async def today(_uid):
        return 20

    monkeypatch.setattr(repository, "product_title", product_title)
    monkeypatch.setattr(repository, "quotes_created_today", today)
    res = client.post("/api/v1/quotes/", json={
        "product_id": PID, "quantity": 5, "destination_country": "US",
    })
    assert res.status_code == 429


def test_customer_sees_only_own_quotes_even_with_all(client, monkeypatch):
    seen = {}

    async def list_quotes(user_id, limit=100):
        seen["user_id"] = user_id
        return [_quote_row()]

    monkeypatch.setattr(repository, "list_quotes", list_quotes)
    body = client.get("/api/v1/quotes/?all=true").json()
    assert seen["user_id"] == USER.id and body["is_admin"] is False


def test_customer_cannot_reply(client):
    res = client.post(f"/api/v1/quotes/{_quote_row()['id']}/reply",
                      json={"quoted_unit_usd": 1.5})
    assert res.status_code == 403


def test_admin_reply(client, monkeypatch):
    app.dependency_overrides[current_user] = lambda: ADMIN  # case-insensitive email match

    async def reply(qid, status, unit, ship, text):
        return _quote_row(status=status, quoted_unit_usd=unit,
                          quoted_shipping_usd=ship, reply=text, replied_at=NOW)

    monkeypatch.setattr(repository, "reply_quote", reply)
    res = client.post(f"/api/v1/quotes/{_quote_row()['id']}/reply",
                      json={"quoted_unit_usd": 1.5, "quoted_shipping_usd": 0.8, "reply": " ok "})
    assert res.status_code == 200
    assert res.json()["quoted_unit_usd"] == 1.5 and res.json()["reply"] == "ok"


def test_admin_quote_needs_a_price(client):
    app.dependency_overrides[current_user] = lambda: ADMIN
    res = client.post(f"/api/v1/quotes/{_quote_row()['id']}/reply", json={"reply": "hi"})
    assert res.status_code == 422
