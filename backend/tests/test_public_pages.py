"""Public SEO pages: only each day's free #1, never the paid list."""
import json
from datetime import date, timedelta

from fastapi.testclient import TestClient

from app import db
from app.main import app
from app.routers import winners
from app.winners import store

D0 = date.today()
A, B, C = ("aaaaaaaa-0000-0000-0000-000000000001", "bbbbbbbb-0000-0000-0000-000000000002",
           "cccccccc-0000-0000-0000-000000000003")


def _row(day, rank, pid, title="Posture Corrector", image="https://img/x.jpg", category="health"):
    return {"pick_date": day, "rank": rank, "tier": "winner", "total": 90 - rank, "product_id": pid,
            "breakdown": json.dumps({"demand": 17}), "reasons": json.dumps(["r1", "r2", "r3", "r4"]),
            "signals": json.dumps({"trend": "growing", "advertisers": 7, "max_days_running": 30}),
            "title": title, "image_url": image, "category": category, "price_usd": 29.9,
            "attributes": json.dumps({"angles": [{"angle": "Gift", "hook": "She'll love it"}]})}


async def test_top_picks_takes_first_shown_product_per_day(monkeypatch):
    rows = [
        _row(D0, 1, A, image=None),            # no picture -> skipped, like picks()
        _row(D0, 2, B),                         # so B is today's public #1
        _row(D0, 3, C),
        _row(D0 - timedelta(days=1), 1, C),
    ]

    async def fetch(*_a):
        return rows

    monkeypatch.setattr(db, "fetch", fetch)
    top = await store.top_picks("US", D0 - timedelta(days=60))
    assert [(r["pick_date"], r["product_id"]) for r in top] == [(D0, B), (D0 - timedelta(days=1), C)]


def _client(monkeypatch, rows):
    async def top(_m, _since):
        return rows

    async def none(*_a, **_k):
        return None

    monkeypatch.setattr(store, "top_picks", top)
    monkeypatch.setattr(db, "connect", none)
    monkeypatch.setattr(db, "disconnect", none)
    return TestClient(app)


def test_public_top_shape_has_no_paid_data(monkeypatch):
    with _client(monkeypatch, [_row(D0, 1, A)]) as c:
        body = c.get("/api/v1/winners/public/top?market=fr").json()
    assert body["market"] == "FR" and len(body["picks"]) == 1
    pick = body["picks"][0]
    assert pick["product_id"] == A and pick["angle"]["angle"] == "Gift" and len(pick["reasons"]) == 3
    for paid in ("supplier_url", "ad_url", "store_url", "links", "cost_usd"):
        assert paid not in pick


def test_public_product_only_for_past_number_ones(monkeypatch):
    rows = [_row(D0, 1, A), _row(D0 - timedelta(days=3), 1, A), _row(D0 - timedelta(days=1), 1, B)]
    with _client(monkeypatch, rows) as c:
        ok = c.get(f"/api/v1/winners/public/products/{A}?market=US").json()
        assert ok["featured_on"] == [D0.isoformat(), (D0 - timedelta(days=3)).isoformat()]
        assert c.get(f"/api/v1/winners/public/products/{C}?market=US").status_code == 404
        assert c.get("/api/v1/winners/public/top?market=ZZ").status_code == 400


def test_public_top_is_cached(monkeypatch):
    calls = {"n": 0}

    async def top(_m, _since):
        calls["n"] += 1
        return []

    monkeypatch.setattr(store, "top_picks", top)
    with _client(monkeypatch, []) as c:
        monkeypatch.setattr(store, "top_picks", top)
        c.get("/api/v1/winners/public/top?market=US")
        c.get("/api/v1/winners/public/top?market=US")
    assert calls["n"] == 1 and winners.PUBLIC_TTL_S >= 600
