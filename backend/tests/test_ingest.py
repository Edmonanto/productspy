"""Phase 2: scoring maths, provider parsing, and the ingestion loop."""
from datetime import datetime, timezone

import pytest

from app import scoring
from app.providers.aliexpress import AliExpressProvider, _sign
from app.providers.apify import ApifyProvider
from app.schemas import AdSignal, Product, Score

NOW = datetime.now(timezone.utc)


def make_product(**overrides) -> Product:
    base = dict(
        id="p1", title="LED Dog Collar", image_url=None,
        product_url="https://example.com/1", category="pets",
        price_usd=24.99, cost_usd=4.20, source="aliexpress",
        score=None, suppliers=[], ad_signals=[],
    )
    base.update(overrides)
    return Product(**base)


# ── demand ──────────────────────────────────────────────────────────────────
def test_demand_unknown_is_neutral_not_zero():
    # None means "no data", which must not be punished like zero sales.
    assert scoring.demand_score(None) == scoring.UNKNOWN
    assert scoring.demand_score(0) == 0


def test_demand_is_monotonic_and_capped():
    scores = [scoring.demand_score(n) for n in (1, 100, 1_000, 10_000, 10_000_000)]
    assert scores == sorted(scores)
    assert scores[-1] == 100


# ── trend (the signal we build ourselves) ───────────────────────────────────
def test_trend_without_history_is_neutral():
    assert scoring.trend_score(500, None) == scoring.UNKNOWN
    assert scoring.trend_score(None, 500) == scoring.UNKNOWN


def test_trend_rewards_growth_and_punishes_decline():
    flat = scoring.trend_score(100, 100)
    growing = scoring.trend_score(150, 100)
    declining = scoring.trend_score(50, 100)
    assert declining < flat < growing
    assert flat == scoring.UNKNOWN
    assert growing == 100  # +50% hits TREND_CEILING


def test_trend_handles_zero_previous_without_dividing_by_zero():
    assert scoring.trend_score(10, 0) == 75
    assert scoring.trend_score(0, 0) == scoring.UNKNOWN


# ── margin / competition ────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "price,cost,expected",
    [(100.0, 30.0, 100), (100.0, 65.0, 50), (100.0, 100.0, 0), (None, 5.0, 0)],
)
def test_margin_score(price, cost, expected):
    assert scoring.margin_score(price, cost) == expected


def test_competition_unknown_is_neutral():
    assert scoring.competition_score([]) == scoring.UNKNOWN


def test_competition_inverts_ad_volume():
    few = [AdSignal(platform="tiktok", ad_count=10, last_seen_at=NOW)]
    many = [AdSignal(platform="tiktok", ad_count=400, last_seen_at=NOW)]
    assert scoring.competition_score(few) > scoring.competition_score(many)


# ── composite ───────────────────────────────────────────────────────────────
def test_weights_sum_to_one():
    assert abs(sum(scoring.WEIGHTS.values()) - 1.0) < 1e-9


def test_score_product_preserves_existing_summary():
    product = make_product(
        score=Score(overall_score=1, demand_score=1, margin_score=1,
                    competition_score=1, trend_score=1, ai_summary="keep me")
    )
    assert scoring.score_product(product, 500, 400).ai_summary == "keep me"


def test_score_product_uses_all_signals():
    product = make_product(
        ad_signals=[AdSignal(platform="tiktok", ad_count=20, last_seen_at=NOW)]
    )
    score = scoring.score_product(product, orders_count=5000, previous_orders=2500)
    assert score.margin_score == 100          # 83% margin
    assert score.trend_score == 100           # doubled orders
    assert score.demand_score > 80
    assert score.overall_score > 80


# ── AliExpress ──────────────────────────────────────────────────────────────
def test_signature_is_deterministic_and_order_independent():
    a = _sign({"b": "2", "a": "1"}, "secret")
    b = _sign({"a": "1", "b": "2"}, "secret")
    assert a == b == a.upper()


def test_aliexpress_parses_products():
    body = {
        "aliexpress_affiliate_hotproduct_query_response": {
            "resp_result": {"result": {"products": {"product": [{
                "product_id": "123",
                "product_title": "Magnetic Phone Stand",
                "product_detail_url": "https://aliexpress.com/item/123.html",
                "product_main_image_url": "https://img/1.jpg",
                "first_level_category_name": "Phones",
                "target_original_price": "19.99",
                "target_sale_price": "4.50",
                "lastest_volume": 3200,
            }]}}}
        }
    }
    [product] = AliExpressProvider(app_key="k", app_secret="s").parse(body)
    assert product.external_id == "123"
    assert product.price_usd == 19.99
    assert product.cost_usd == 4.50
    assert product.orders_count == 3200
    assert product.source == "aliexpress"


def test_aliexpress_returns_empty_on_error_response():
    provider = AliExpressProvider(app_key="k", app_secret="s")
    assert provider.parse({"error_response": {"msg": "invalid signature"}}) == []


def test_aliexpress_skips_unconfigured():
    assert AliExpressProvider(app_key="", app_secret="").configured is False


# ── Apify ───────────────────────────────────────────────────────────────────
def test_apify_maps_varied_field_names():
    provider = ApifyProvider(actor_id="x/y", source="amazon", token="t")
    [product] = provider.parse([{
        "asin": "B01", "title": "Desk Mat", "url": "https://a.com/B01",
        "price": "$29.99", "sold": "1,200", "adCount": 15,
    }])
    assert product.external_id == "B01"
    assert product.price_usd == 29.99      # strips $
    assert product.orders_count == 1200    # strips comma
    assert product.ad_count == 15
    assert product.ad_platform == "amazon"


def test_apify_skips_items_missing_identity():
    provider = ApifyProvider(actor_id="x/y", source="amazon", token="t")
    assert provider.parse([{"price": 10}, "not-a-dict", {"title": "no id"}]) == []
