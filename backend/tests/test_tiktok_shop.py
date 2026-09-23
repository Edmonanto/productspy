"""TikTok Shop provider — tested against real captured API responses."""
import json
import pathlib

import pytest

from app import config
from app.providers.tiktok_shop import TikTokShopProvider

F = pathlib.Path(__file__).parent / "fixtures"
SEARCH = json.loads((F / "tiktok_search.json").read_text())
DETAIL = json.loads((F / "tiktok_detail.json").read_text())
STORE = json.loads((F / "tiktok_store.json").read_text())


def provider(**kw):
    kw.setdefault("keywords", ["cat"])
    kw.setdefault("seller_ids", [])
    return TikTokShopProvider(base_url="https://x/shop", token="t", **kw)


# ── search parsing ──────────────────────────────────────────────────────────
def test_parses_real_search_payload():
    products = provider().parse_products(SEARCH)
    assert products
    p = products[0]
    assert p.source == "tiktok"
    assert p.external_id.isdigit()
    assert p.product_url.endswith(p.external_id)


def test_every_product_has_demand_and_retail_price():
    """sold_count and price drive demand + margin; both are 100% in practice."""
    for p in provider().parse_products(SEARCH):
        assert p.orders_count is not None, f"{p.external_id} missing sold_count"
        assert p.price_usd is not None, f"{p.external_id} missing price"
        assert p.price_usd > 0


def test_price_is_observed_not_derived():
    """Unlike 1688, TikTok reports a real USD retail price."""
    p = provider().parse_products(SEARCH)[0]
    raw = SEARCH["data"]["products"][0]["price"]["current"]
    assert p.price_usd == float(raw)


def test_cost_is_never_invented():
    """TikTok exposes no supplier cost — leave it None rather than guess."""
    assert all(p.cost_usd is None for p in provider().parse_products(SEARCH))


def test_non_usd_price_is_dropped_not_misread():
    """A localised storefront must not be read as dollars."""
    body = {"code": "success", "data": {"products": [{
        "product_id": "1", "title": "X",
        "price": {"currency": "GBP", "current": "9.99"}, "sold_count": 5,
    }]}}
    [p] = provider().parse_products(body)
    assert p.price_usd is None
    assert p.orders_count == 5   # the rest of the record still survives


def test_store_products_use_the_same_shape():
    """store/products returns the same payload as search — one parser."""
    products = provider().parse_products(STORE)
    assert products
    assert all(p.source == "tiktok" and p.orders_count is not None for p in products)


def test_error_body_returns_empty():
    assert provider().parse_products({"code": "error", "msg": "调用失败"}) == []


def test_missing_products_key_does_not_raise():
    assert provider().parse_products({"code": "success", "data": {}}) == []


def test_skips_entries_without_id_or_title():
    body = {"code": "success", "data": {"products": [
        {"title": "no id"}, {"product_id": "1"}, "junk",
    ]}}
    assert provider().parse_products(body) == []


# ── detail enrichment ───────────────────────────────────────────────────────
def test_detail_overlays_sale_price_and_sold_count():
    p = provider().parse_products(SEARCH)[0]
    provider().apply_detail(p, DETAIL)
    min_price = DETAIL["data"]["product_info"]["promotion_model"]["promotion_product_price"]["min_price"]
    assert p.price_usd == float(min_price["sale_price_decimal"])
    assert p.orders_count == int(
        DETAIL["data"]["product_info"]["product_model"]["sold_count"]
    )


def test_detail_never_lowers_a_known_sold_count():
    p = provider().parse_products(SEARCH)[0]
    p.orders_count = 999_999
    provider().apply_detail(p, DETAIL)
    assert p.orders_count == 999_999


def test_detail_error_leaves_product_untouched():
    p = provider().parse_products(SEARCH)[0]
    before = (p.title, p.price_usd, p.orders_count)
    provider().apply_detail(p, {"code": "error", "msg": "调用失败"})
    assert (p.title, p.price_usd, p.orders_count) == before


def test_detail_ignores_non_usd_sale_price():
    p = provider().parse_products(SEARCH)[0]
    original = p.price_usd
    body = {"code": "success", "data": {"product_info": {"promotion_model": {
        "promotion_product_price": {"min_price": {
            "currency_name": "EUR", "sale_price_decimal": "1.00"}}}}}}
    provider().apply_detail(p, body)
    assert p.price_usd == original


# ── configuration ───────────────────────────────────────────────────────────
def test_needs_token_and_at_least_one_source():
    assert TikTokShopProvider(base_url="u", token="", keywords=["a"], seller_ids=[]).configured is False
    assert TikTokShopProvider(base_url="u", token="t", keywords=[], seller_ids=[]).configured is False
    assert TikTokShopProvider(base_url="u", token="t", keywords=[], seller_ids=["7495"]).configured is True
    assert TikTokShopProvider(base_url="u", token="t", keywords=["a"], seller_ids=[]).configured is True


def test_registry_enables_tiktok(monkeypatch):
    from app.providers.registry import enabled_providers
    for k in ("ALIBABA1688_APP_KEY","ALIBABA1688_APP_SECRET","ALIEXPRESS_APP_KEY",
              "ALIEXPRESS_APP_SECRET","AGG1688_SEARCH_URL"):
        monkeypatch.setattr(config, k, "")
    monkeypatch.setattr(config, "TIKTOK_TOKEN", "t")
    monkeypatch.setattr(config, "TIKTOK_KEYWORDS", "cat")
    monkeypatch.setattr(config, "TIKTOK_SELLER_IDS", "")
    assert [p.name for p in enabled_providers()] == ["tiktok"]
