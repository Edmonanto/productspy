"""1688 parsing (against real captured payloads) and 1688-signal scoring."""
import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from app import scoring
from app.sources.ali1688 import parser

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


# ── search ──────────────────────────────────────────────────────────────────
def test_parse_search_page():
    page = parser.parse_search(_load("search_1688.json"), "衣服", 1)
    assert page.total_found == 2000
    assert page.has_more is True
    assert [o.offer_id for o in page.offers] == ["724364863244", "840138217750", "1039701527597"]


def test_parse_search_offer_fields():
    first = parser.parse_search(_load("search_1688.json"), "衣服", 1).offers[0]
    assert "<font" not in first.title and "衣服" in first.title
    assert first.price_cny == 28.0
    assert first.sales_count == 7900
    assert first.repurchase_rate == pytest.approx(0.12)
    assert first.is_ad is True  # P4P block
    assert first.image_url.startswith("https://cbu01.alicdn.com/")
    assert first.product_url == "https://detail.1688.com/offer/724364863244.html"
    assert first.seller.company_name == "惠州市潮衫服饰有限公司"
    assert first.seller.location == "广东 惠州市"
    assert first.seller.years_on_platform == 4


def test_parse_search_skips_malformed_cards():
    payload = {"data": {"data": {"OFFER": {"found": 1, "items": [{"data": {}}, {}]}}}}
    assert parser.parse_search(payload, "x", 1).offers == []


def test_parse_search_empty_payload():
    page = parser.parse_search({}, "x", 1)
    assert page.offers == [] and page.total_found == 0


# ── detail ──────────────────────────────────────────────────────────────────
def test_parse_detail():
    d = parser.parse_detail(_load("detail_1688.json"))
    assert d is not None
    assert d.offer_id == "845599468116"
    assert d.price_min_cny == 3.97 and d.price_max_cny == 17.86
    assert d.price_tiers[0].min_quantity == 1
    assert d.min_order_quantity == 1
    assert d.sales_count == 71
    assert len(d.images) == 5
    assert d.video_url and d.video_url.endswith(".mp4")
    assert d.ships_from == "江苏宿迁"
    assert d.ship_within_days == 2
    assert d.free_shipping is True
    assert d.seller.company_name.startswith("济南高新区阁昆种子经销部")
    assert d.attributes  # propsList
    assert "7天无理由退货" in d.services


def test_parse_detail_without_offer_id():
    assert parser.parse_detail({"data": {}}) is None


# ── field helpers ───────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "text,expected",
    [("全网7900+件", 7900), ("已售1.2万+件", 12000), ("已售20+件", 20), (71, 71), ("", None), (None, None)],
)
def test_parse_count(text, expected):
    assert parser.parse_count(text) == expected


@pytest.mark.parametrize(
    "text,expected", [("3.97-17.86", (3.97, 17.86)), ("28", (28.0, 28.0)), ("", (None, None))]
)
def test_parse_price_range(text, expected):
    assert parser.parse_price_range(text) == expected


# ── scoring ─────────────────────────────────────────────────────────────────
def test_demand_rises_with_sales():
    assert scoring.demand_score(10_000, 0.12) > scoring.demand_score(100, 0.12) > scoring.demand_score(0, None)
    assert scoring.demand_score(10**9, 1.0) == 100


@pytest.mark.parametrize("cost,expected", [(1.0, 100), (2.0, 100), (40.0, 0), (80.0, 0), (None, 0)])
def test_margin_score_bounds(cost, expected):
    assert scoring.margin_score(cost) == expected


def test_margin_prefers_cheaper_items():
    assert scoring.margin_score(3.0) > scoring.margin_score(15.0)


def test_trend_neutral_without_history():
    assert scoring.trend_score([]) == 50
    assert scoring.trend_score([(date(2026, 9, 1), 100)]) == 50


def test_trend_direction():
    start = date(2026, 9, 1)
    growing = [(start, 1000), (start + timedelta(days=7), 1100)]   # +10%/week
    shrinking = [(start, 1000), (start + timedelta(days=7), 900)]
    assert scoring.trend_score(growing) == 75
    assert scoring.trend_score(shrinking) < 50


def test_overall_weights_sum_to_one():
    assert abs(sum(scoring.WEIGHTS.values()) - 1.0) < 1e-9


def test_summary_is_factual():
    s = scoring.Signals(sales_count=7900, repurchase_rate=0.12, cost_usd=3.92,
                        snapshots=[], ad_signals=[], location="广东 惠州市")
    assert scoring.summary(s) == "7,900+ sold on 1688 · 12% repurchase rate · $3.92 unit cost · ships from 广东 惠州市"
