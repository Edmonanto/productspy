"""1688 aggregator provider — tested against real captured API responses.

The fixtures in tests/fixtures/ are trimmed copies of actual responses from
the live endpoints, not hand-written guesses, so a schema change upstream
shows up here rather than as an empty ingestion run.
"""
import json
import pathlib

import pytest

from app import config
from app.providers.aggregator1688 import (
    Aggregator1688Provider, parse_cn_count, parse_price, strip_html,
)

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
SEARCH = json.loads((FIXTURES / "search_1688.json").read_text())
DETAIL = json.loads((FIXTURES / "detail_1688.json").read_text())


@pytest.fixture(autouse=True)
def rates(monkeypatch):
    monkeypatch.setattr(config, "CNY_PER_USD", 7.15)
    monkeypatch.setattr(config, "WHOLESALE_MARKUP", 3.0)
    monkeypatch.setattr(config, "AGG1688_INCLUDE_ADS", False)


def provider(**kw):
    return Aggregator1688Provider(
        search_url="http://x/search", search_token="t",
        detail_url="http://y/detail", detail_token="t2",
        keywords=["衣服"], **kw,
    )


# ── helpers ─────────────────────────────────────────────────────────────────
def test_strip_html_removes_keyword_highlighting():
    # Real search titles wrap the matched keyword in <font> tags.
    assert strip_html("Polo衫<font color=red>衣服</font>刺绣") == "Polo衫衣服刺绣"
    assert strip_html("") == ""


@pytest.mark.parametrize("text,expected", [
    ("已售2200+件", 2200),
    ("全网7900+件", 7900),
    ("已售1.3万+件", 13000),   # 万 = 10,000 — naive parsing reads this as 1
    ("已售70+件", 70),
    ("2.5亿", 250_000_000),
    ("暂无销量", None),
    (None, None),
])
def test_parse_cn_count(text, expected):
    assert parse_cn_count(text) == expected


@pytest.mark.parametrize("value,expected", [
    ("28", 28.0), ("3.97", 3.97),
    ("3.97-17.86", 3.97),   # range -> low end, the volume price
    (14, 14.0), ("", None), (None, None),
])
def test_parse_price(value, expected):
    assert parse_price(value) == expected


# ── search parsing (real payload) ───────────────────────────────────────────
def test_parses_real_search_payload():
    products = provider().parse_search(SEARCH)
    assert products, "fixture should yield offers"
    p = products[0]
    assert p.source == "1688"
    assert p.external_id.isdigit()
    assert "<font" not in p.title
    assert p.cost_usd and p.cost_usd > 0
    assert p.product_url == f"https://detail.1688.com/offer/{p.external_id}.html"


def test_every_offer_has_the_fields_scoring_needs():
    """cost and orders drive 60% of the score; missing them scores neutral."""
    for p in provider().parse_search(SEARCH):
        assert p.cost_usd is not None, f"{p.external_id} has no cost"
        assert p.orders_count is not None, f"{p.external_id} has no orders"


def test_currency_conversion_and_derived_retail():
    p = provider().parse_search(SEARCH)[0]
    # price_usd is derived, not observed — 3x the wholesale cost.
    assert p.price_usd == round(p.cost_usd * 3.0, 2)


def test_p4p_ads_excluded_by_default():
    """Paid placement must not be counted as organic demand."""
    ids = {p.external_id for p in provider().parse_search(SEARCH)}
    ad_ids = {
        str(w["data"]["offerId"]) for w in SEARCH["data"]["data"]["OFFER"]["items"]
        if w["data"].get("isP4P") or w["data"].get("block") == "P4P"
    }
    assert not (ids & ad_ids)


def test_ads_included_when_opted_in(monkeypatch):
    monkeypatch.setattr(config, "AGG1688_INCLUDE_ADS", True)
    with_ads = len(provider().parse_search(SEARCH))
    monkeypatch.setattr(config, "AGG1688_INCLUDE_ADS", False)
    assert with_ads >= len(provider().parse_search(SEARCH))


def test_error_body_returns_empty():
    """mtop returns errors with HTTP 200 — must not look like success."""
    assert provider().parse_search({"code": "fail", "msg": "token invalid"}) == []


def test_missing_offer_block_does_not_raise():
    assert provider().parse_search({"code": "success", "data": {}}) == []


def test_skips_entries_without_id_or_title():
    body = {"code": "success", "data": {"data": {"OFFER": {"items": [
        {"data": {"title": "no id"}},
        {"data": {"offerId": 1}},
        {"not_data": {}},
    ]}}}}
    assert provider().parse_search(body) == []


# ── detail enrichment (real payload) ────────────────────────────────────────
def test_detail_overlays_tiered_price_and_sold_count():
    products = provider().parse_search(SEARCH)
    p = products[0]
    before_cost = p.cost_usd
    provider().apply_detail(p, DETAIL)
    # Fixture's cheapest tier is 3.97 CNY at beginAmount 1.
    assert p.cost_usd == round(3.97 / 7.15, 2)
    assert p.cost_usd != before_cost
    assert p.price_usd == round(p.cost_usd * 3.0, 2)


def test_detail_never_lowers_a_known_order_count():
    p = provider().parse_search(SEARCH)[0]
    p.orders_count = 99999
    provider().apply_detail(p, DETAIL)
    assert p.orders_count == 99999


def test_detail_with_junk_body_leaves_product_untouched():
    p = provider().parse_search(SEARCH)[0]
    snapshot = (p.cost_usd, p.title, p.orders_count)
    provider().apply_detail(p, {"ret": ["FAIL"]})
    assert (p.cost_usd, p.title, p.orders_count) == snapshot


# ── configuration ───────────────────────────────────────────────────────────
def test_requires_url_token_and_keywords():
    assert Aggregator1688Provider(search_url="", search_token="t", keywords=["a"]).configured is False
    assert Aggregator1688Provider(search_url="u", search_token="", keywords=["a"]).configured is False
    assert Aggregator1688Provider(search_url="u", search_token="t", keywords=[]).configured is False
    assert Aggregator1688Provider(search_url="u", search_token="t", keywords=["a"]).configured is True


def test_province_is_not_stored_as_a_category():
    """1688's payload carries the supplier's province, not a product category.

    Storing it in `category` gave every 1688 row a value like 浙江, which no
    category filter in the dashboard could ever match — so selecting any
    category returned nothing, and the frontend silently swapped in demo
    products.
    """
    products = provider().parse_search(SEARCH)
    assert products, "fixture should yield offers"
    assert all(p.category is None for p in products)
