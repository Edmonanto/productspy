"""Product-page sourcing detail (parse + lazy cached fetch) and quote requests.

No database and no paid calls: repository functions and the provider are
replaced per test.
"""
import json
import pathlib
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import config, db, repository
from app.auth import CurrentUser, current_user
from app.main import app
from app.providers.aggregator1688 import Aggregator1688Provider
from app.schemas import Product
from app.services import product_details

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
DETAIL = json.loads((FIXTURES / "detail_1688.json").read_text(encoding="utf-8"))
NOW = datetime.now(timezone.utc)

USER = CurrentUser(id="11111111-1111-1111-1111-111111111111", email="buyer@x.com",
                   name="Buyer", avatar_url=None)
ADMIN = CurrentUser(id="33333333-3333-3333-3333-333333333333", email="Boss@X.com",
                    name="Boss", avatar_url=None)
PID = "22222222-2222-2222-2222-222222222222"


def product(**kw) -> Product:
    base = dict(id=PID, title="猫窝", title_en="Cat bed", image_url=None,
                product_url="https://detail.1688.com/offer/1.html", category=None,
                price_usd=6.0, cost_usd=2.0, price_is_derived=True, source="1688",
                score=None)
    base.update(kw)
    return Product(**base)


@pytest.fixture(autouse=True)
def settings(monkeypatch):
    monkeypatch.setattr(config, "CNY_PER_USD", 7.0)
    monkeypatch.setattr(config, "DETAIL_TTL_DAYS", 7.0)
    monkeypatch.setattr(config, "AGG1688_DETAIL_ON_VIEW", True)
    monkeypatch.setattr(config, "AGG1688_DETAIL_URL", "http://y/detail")
    monkeypatch.setattr(config, "AGG1688_DETAIL_TOKEN", "t")
    monkeypatch.setattr(config, "SHIPPING_USD_BASE", 3.0)
    monkeypatch.setattr(config, "SHIPPING_USD_PER_KG", 10.0)
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


# ── parsing ─────────────────────────────────────────────────────────────────
def test_parse_detail_info_from_real_payload():
    d = Aggregator1688Provider.parse_detail_info(DETAIL)
    assert d is not None
    assert d["price_tiers"] and d["moq"] == d["price_tiers"][0]["min_qty"]
    assert [t["min_qty"] for t in d["price_tiers"]] == sorted(t["min_qty"] for t in d["price_tiers"])
    assert d["images"] and all(u.startswith("http") for u in d["images"])
    assert isinstance(d["attributes"], dict)
    assert d["weight_kg"] is None or d["weight_kg"] > 0


def test_parse_detail_info_rejects_non_detail():
    assert Aggregator1688Provider.parse_detail_info({"code": "error"}) is None


def test_to_model_converts_tiers_and_estimates_shipping():
    m = product_details.to_model(
        {"price_tiers": [{"min_qty": 2, "price_cny": 14.0}], "weight_kg": 0.5, "junk": 1},
        fetched_at=NOW,
    )
    assert m.price_tiers[0].price_usd == 2.0          # 14 CNY / 7
    assert m.shipping_estimate_usd == 8.0             # 3 + 0.5 kg * 10
    assert m.cny_per_usd == 7.0


# ── lazy, cached fetch ──────────────────────────────────────────────────────
def _stored(monkeypatch, details, fetched_at):
    async def row(_pid):
        return {"external_id": "845599468116", "details": details,
                "details_fetched_at": fetched_at}
    monkeypatch.setattr(repository, "product_details", row)


async def test_fresh_details_cost_no_call(monkeypatch):
    _stored(monkeypatch, json.dumps({"moq": 3, "price_tiers": []}), NOW)

    async def must_not_fetch(*_a):
        raise AssertionError("fresh detail must not spend a call")

    monkeypatch.setattr(product_details, "_fetch", must_not_fetch)
    out = await product_details.attach_details(product())
    assert out.details.moq == 3


async def test_stale_details_are_refetched(monkeypatch):
    _stored(monkeypatch, None, NOW - timedelta(days=30))

    async def fetch(_pid, offer_id):
        assert offer_id == "845599468116"
        return {"moq": 5, "price_tiers": [{"min_qty": 5, "price_cny": 7.0}]}

    async def get_product(_pid):
        return product(cost_usd=1.0)

    monkeypatch.setattr(product_details, "_fetch", fetch)
    monkeypatch.setattr(repository, "get_product", get_product)
    out = await product_details.attach_details(product())
    assert out.details.moq == 5 and out.cost_usd == 1.0


async def test_fetch_failure_still_renders_stored(monkeypatch):
    _stored(monkeypatch, {"moq": 9}, NOW - timedelta(days=30))

    async def boom(*_a):
        raise RuntimeError("provider down")

    monkeypatch.setattr(product_details, "_fetch", boom)
    out = await product_details.attach_details(product())
    assert out.details.moq == 9


async def test_detail_on_view_can_be_switched_off(monkeypatch):
    monkeypatch.setattr(config, "AGG1688_DETAIL_ON_VIEW", False)
    _stored(monkeypatch, None, None)

    async def must_not_fetch(*_a):
        raise AssertionError("disabled")

    monkeypatch.setattr(product_details, "_fetch", must_not_fetch)
    assert (await product_details.attach_details(product())).details is None


async def test_non_1688_products_are_untouched():
    p = product(source="amazon")
    assert (await product_details.attach_details(p)).details is None


# ── quotes ──────────────────────────────────────────────────────────────────
def _quote_row(**kw):
    base = dict(id="44444444-4444-4444-4444-444444444444", user_id=USER.id,
                user_email=USER.email, product_id=PID, product_title="Cat bed",
                quantity=200, destination_country="US", target_price_usd=None,
                notes="", status="open", quoted_unit_usd=None,
                quoted_shipping_usd=None, reply="", created_at=NOW, replied_at=None)
    base.update(kw)
    return base


def test_request_quote(client, monkeypatch):
    seen = {}

    async def get_product(_pid):
        return product()

    async def today(_uid):
        return 0

    async def create(**kw):
        seen.update(kw)
        return _quote_row(quantity=kw["quantity"])

    monkeypatch.setattr(repository, "get_product", get_product)
    monkeypatch.setattr(repository, "quotes_created_today", today)
    monkeypatch.setattr(repository, "create_quote", create)

    res = client.post("/api/v1/quotes/", json={
        "product_id": PID, "quantity": 200, "destination_country": " US ", "notes": " fast ",
    })
    assert res.status_code == 201
    assert res.json()["status"] == "open"
    assert seen["product_title"] == "Cat bed"          # English title stored
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
    async def get_product(_pid):
        return product()

    async def today(_uid):
        return 20

    monkeypatch.setattr(repository, "get_product", get_product)
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
