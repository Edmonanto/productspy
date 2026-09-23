"""/matches — the review queue API.

Confirming is the only place a match changes a product, so these focus on
what confirm does and on what the endpoints refuse.
"""
import pytest
from fastapi.testclient import TestClient

from app import db, repository, scoring
from app.auth import CurrentUser, current_user
from app.main import app
from app.schemas import Product

USER = CurrentUser(id="11111111-1111-1111-1111-111111111111",
                   email="e@x.com", name="Edmond", avatar_url=None)


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


ROW = {
    "id": 7, "confidence": 0.72, "method": "title+price", "status": "candidate",
    "evidence": '{"shared_tokens":["plush","tunnel"],"price_ratio":4.64}',
    "created_at": None,
    "retail_id": "aaaaaaaa-0000-0000-0000-000000000001",
    "retail_title": "Cute Fuzzy Plush Pet Tunnel Bed",
    "retail_image": "https://img/r.jpg", "retail_url": "https://tiktok/1",
    "retail_price": 31.19, "retail_source": "tiktok", "retail_orders": 2362,
    "supplier_id": "bbbbbbbb-0000-0000-0000-000000000002",
    "supplier_title": "猫窝隧道", "supplier_title_en": "plush cat tunnel bed",
    "supplier_image": "https://img/s.jpg", "supplier_url": "https://1688/2",
    "supplier_cost": 6.72, "supplier_source": "1688",
}


def test_list_returns_both_sides_and_projected_margin(client, monkeypatch):
    async def list_matches(status, limit):
        return [ROW]

    async def counts():
        return {"candidate": 1}

    monkeypatch.setattr(repository, "list_matches", list_matches)
    monkeypatch.setattr(repository, "match_counts", counts)

    body = client.get("/api/v1/matches/?status=candidate").json()
    item = body["items"][0]
    assert item["retail"]["price_usd"] == 31.19
    assert item["supplier"]["cost_usd"] == 6.72
    # (31.19 - 6.72) / 31.19 = 78.45% -> 78
    assert item["projected_margin_pct"] == 78
    assert item["evidence"]["shared_tokens"] == ["plush", "tunnel"]
    assert body["counts"] == {"candidate": 1}


def test_projected_margin_is_not_applied_by_listing(client, monkeypatch):
    """Listing must never write anything — it only previews."""
    applied = []

    async def list_matches(status, limit):
        return [ROW]

    async def counts():
        return {}

    async def apply(*a):
        applied.append(a)

    monkeypatch.setattr(repository, "list_matches", list_matches)
    monkeypatch.setattr(repository, "match_counts", counts)
    monkeypatch.setattr(repository, "apply_supplier_cost", apply)

    client.get("/api/v1/matches/")
    assert applied == []


def test_invalid_status_is_rejected(client):
    assert client.get("/api/v1/matches/?status=maybe").status_code == 400


def test_confirm_applies_cost_and_rescores(client, monkeypatch):
    """The payoff: the retail row gains a real cost and a real margin."""
    state = {}

    async def get_match(mid):
        return {**ROW, "retail_id": ROW["retail_id"], "supplier_cost": 6.72,
                "status": "candidate"}

    async def apply_supplier_cost(retail_id, cost):
        state["applied"] = (retail_id, cost)

    async def set_status(mid, status):
        state["status"] = status

    async def get_product(pid):
        # Reflects the cost just written.
        return Product(
            id=pid, title="Cute Fuzzy Plush Pet Tunnel Bed", image_url=None,
            product_url="https://tiktok/1", category=None,
            price_usd=31.19, cost_usd=6.72, source="tiktok",
            score=None, suppliers=[], ad_signals=[],
        )

    async def current_orders(pid):
        return 2362

    async def orders_at(pid, days):
        return None

    async def save_score(pid, score):
        state["score"] = score

    for name, fn in [
        ("get_match", get_match), ("apply_supplier_cost", apply_supplier_cost),
        ("set_match_status", set_status), ("get_product", get_product),
        ("current_orders", current_orders), ("orders_at", orders_at),
        ("save_score", save_score),
    ]:
        monkeypatch.setattr(repository, name, fn)

    body = client.post("/api/v1/matches/7/confirm").json()

    assert state["applied"] == (ROW["retail_id"], 6.72)
    assert state["status"] == "confirmed"
    # Margin is now observed, not the neutral unknown it was before.
    assert state["score"].margin_score != scoring.UNKNOWN
    assert state["score"].margin_score == scoring.margin_score(31.19, 6.72)
    assert body["margin_score"] == state["score"].margin_score


def test_confirm_refuses_when_supplier_has_no_cost(client, monkeypatch):
    async def get_match(mid):
        return {**ROW, "supplier_cost": None, "status": "candidate"}

    applied = []

    async def apply(*a):
        applied.append(a)

    monkeypatch.setattr(repository, "get_match", get_match)
    monkeypatch.setattr(repository, "apply_supplier_cost", apply)

    res = client.post("/api/v1/matches/7/confirm")
    assert res.status_code == 400
    assert applied == []          # nothing written on the refusal path


def test_confirm_unknown_match_404s(client, monkeypatch):
    async def get_match(mid):
        return None

    monkeypatch.setattr(repository, "get_match", get_match)
    assert client.post("/api/v1/matches/999/confirm").status_code == 404


def test_reject_sets_status_without_touching_the_product(client, monkeypatch):
    state = {}
    applied = []

    async def get_match(mid):
        return ROW

    async def set_status(mid, status):
        state["status"] = status

    async def apply(*a):
        applied.append(a)

    monkeypatch.setattr(repository, "get_match", get_match)
    monkeypatch.setattr(repository, "set_match_status", set_status)
    monkeypatch.setattr(repository, "apply_supplier_cost", apply)

    assert client.post("/api/v1/matches/7/reject").status_code == 200
    assert state["status"] == "rejected"
    assert applied == []


def test_endpoints_require_auth(monkeypatch):
    monkeypatch.setattr(db, "connect", lambda: _noop())
    monkeypatch.setattr(db, "disconnect", lambda: _noop())
    with TestClient(app) as c:
        assert c.get("/api/v1/matches/").status_code == 401
        assert c.post("/api/v1/matches/1/confirm").status_code == 401
        assert c.post("/api/v1/matches/1/reject").status_code == 401
