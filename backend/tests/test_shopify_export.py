"""'Add to Shopify': one product as a Shopify import CSV."""
import csv
import io
import json

from app.winners import shopify_export as sx

P = {"id": "22222222-2222-2222-2222-222222222222", "title": "Ski Guards", "category": "fitness",
     "price_usd": 64.0, "cost_usd": 14.5, "image_url": "https://api/x/images/2.jpg?v=1",
     "attributes": json.dumps({})}


def rows(text):
    return list(csv.DictReader(io.StringIO(text)))


def test_csv_has_shopify_columns_and_draft():
    copy = {"title": "Ski Guards for Boots", "intro": "Keeps <edges> safe.", "benefits": ["Fits most skis"],
            "seo_description": "Protect your skis."}
    r = rows(sx.build_csv(P, copy))
    assert len(r) == 1 and list(r[0]) == sx.COLUMNS
    r = r[0]
    assert r["Handle"] == "ski-guards-for-boots" and r["Title"] == "Ski Guards for Boots"
    assert r["Status"] == "draft" and r["Published"] == "FALSE"
    assert r["Variant Price"] == "63.99" and r["Cost per item"] == "14.50"
    assert r["Image Src"] == P["image_url"]
    assert r["Body (HTML)"] == "<p>Keeps &lt;edges&gt; safe.</p><ul><li>Fits most skis</li></ul>"
    assert "ProductSpy" in r["Tags"] and r["Type"] == "Fitness"


def test_price_rules():
    assert sx.suggested_price(64.0, 14.0) == 63.99
    assert sx.suggested_price(None, 8.0) == 23.99          # 3x cost
    assert sx.suggested_price(None, None) is None
    assert sx.suggested_price(29.99, None) == 29.99


async def test_copy_without_ai_uses_template(monkeypatch):
    monkeypatch.setattr(sx, "llm_available", lambda: False)
    c = await sx.product_copy(P)
    assert c["title"] == "Ski Guards" and c["benefits"] == []


async def test_copy_cached(monkeypatch):
    cached = {"title": "Cached", "intro": "x", "benefits": [], "seo_description": ""}
    p = dict(P, attributes=json.dumps({"shopify_copy": cached}))
    monkeypatch.setattr(sx, "llm_available", lambda: True)
    assert await sx.product_copy(p) == cached


def test_route_downloads_csv(monkeypatch):
    from fastapi.testclient import TestClient

    from app import db
    from app.auth import CurrentUser, current_user
    from app.main import app
    from app.winners import store

    async def noop():
        return None

    async def product(pid):
        return dict(P) if pid == P["id"] else None

    async def copy(p):
        return {"title": "Ski Guards", "intro": "", "benefits": [], "seo_description": ""}
    monkeypatch.setattr(db, "connect", noop)
    monkeypatch.setattr(db, "disconnect", noop)
    monkeypatch.setattr(store, "product", product)
    monkeypatch.setattr(sx, "product_copy", copy)
    app.dependency_overrides[current_user] = lambda: CurrentUser(id="u1", email="e@x.com", name="E", avatar_url=None)
    try:
        with TestClient(app) as c:
            r = c.get(f"/api/v1/winners/products/{P['id']}/shopify.csv")
            assert r.status_code == 200 and 'filename="shopify-ski-guards.csv"' in r.headers["content-disposition"]
            assert rows(r.text)[0]["Title"] == "Ski Guards"
            assert c.get("/api/v1/winners/products/33333333-3333-3333-3333-333333333333/shopify.csv").status_code == 404
            assert c.get("/api/v1/winners/products/nope/shopify.csv").status_code == 404
    finally:
        app.dependency_overrides.clear()
