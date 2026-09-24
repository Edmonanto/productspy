"""Phase 2: scoring maths, provider parsing, and the ingestion loop."""
from datetime import datetime, timezone

import pytest

from app import scoring
from app.providers.aliexpress import AliExpressProvider, _sign
from app.schemas import AdSignal, Product, Score

NOW = datetime.now(timezone.utc)


def make_product(**overrides) -> Product:
    base = dict(
        id="p1", title="LED Dog Collar", image_url=None,
        product_url="https://example.com/1", category="pets",
        price_usd=24.99, cost_usd=4.20, price_is_derived=False,
        source="aliexpress", score=None, suppliers=[], ad_signals=[],
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
    [(100.0, 30.0, 100), (100.0, 65.0, 50), (100.0, 100.0, 0), (None, 5.0, scoring.UNKNOWN)],
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



# ── unknown vs genuine zero ─────────────────────────────────────────────────
def test_unknown_margin_is_neutral_not_zero():
    """A source that doesn't publish cost must not be buried.

    TikTok reports retail with no supplier cost; 1688 the reverse. Scoring a
    missing input as zero margin would permanently rank every TikTok product
    below every 1688 one, for a reason that has nothing to do with the product.
    """
    assert scoring.margin_score(24.99, None) == scoring.UNKNOWN
    assert scoring.margin_score(None, 4.20) == scoring.UNKNOWN


def test_genuine_zero_margin_still_scores_zero():
    """Price at or below cost is a real finding, not missing data."""
    assert scoring.margin_score(10.0, 10.0) == 0
    assert scoring.margin_score(10.0, 25.0) == 0


def test_tiktok_shaped_product_is_not_penalised_for_missing_cost():
    product = make_product(price_usd=13.0, cost_usd=None, ad_signals=[])
    score = scoring.score_product(product, orders_count=279, previous_orders=None)
    assert score.margin_score == scoring.UNKNOWN
    # demand is real and strong; overall should reflect that, not be dragged to ~25
    assert score.overall_score > 45


# ── derived vs observed price ───────────────────────────────────────────────
def test_derived_price_scores_margin_as_unknown():
    """A price computed as cost * markup carries no margin information.

    1688 publishes no retail price, so ingestion derives one. Margin then
    reduces to (m-1)/m for every row — the config constant restated. Scored as
    observed it gave every 1688 listing 95/100 and 30% of the composite weight,
    which put untranslated supplier listings above real retail winners.
    """
    assert scoring.margin_score(12.00, 4.00, price_is_derived=True) == scoring.UNKNOWN


def test_identical_numbers_score_differently_by_provenance():
    """The only difference is where the price came from."""
    observed = scoring.margin_score(12.00, 4.00, price_is_derived=False)
    derived = scoring.margin_score(12.00, 4.00, price_is_derived=True)
    assert observed == 95
    assert derived == scoring.UNKNOWN
    assert observed != derived


def test_every_derived_price_scores_the_same_regardless_of_markup():
    """Whatever the markup, a derived margin is not a finding about a product."""
    for markup in (2.0, 3.0, 5.0):
        assert scoring.margin_score(4.0 * markup, 4.0, price_is_derived=True) == (
            scoring.UNKNOWN
        )


def test_derived_flag_does_not_leak_into_other_components():
    """Demand and trend describe real observed sales and must be untouched."""
    derived = make_product(price_usd=12.0, cost_usd=4.0, price_is_derived=True)
    observed = make_product(price_usd=12.0, cost_usd=4.0, price_is_derived=False)
    a = scoring.score_product(derived, orders_count=5000, previous_orders=2500)
    b = scoring.score_product(observed, orders_count=5000, previous_orders=2500)
    assert a.demand_score == b.demand_score
    assert a.trend_score == b.trend_score
    assert a.competition_score == b.competition_score
    assert a.margin_score == scoring.UNKNOWN and b.margin_score == 95


def test_supplier_no_longer_outranks_retail_on_a_constant():
    """The regression that motivated this: a wholesale listing with derived
    margin must not beat a retail listing that genuinely sells more."""
    supplier = make_product(source="1688", price_usd=12.0, cost_usd=4.0,
                            price_is_derived=True)
    retail = make_product(source="tiktok", price_usd=29.99, cost_usd=None)
    s_score = scoring.score_product(supplier, orders_count=800, previous_orders=None)
    r_score = scoring.score_product(retail, orders_count=9000, previous_orders=None)
    assert r_score.overall_score > s_score.overall_score


def test_confirmed_match_restores_a_real_margin():
    """Once a match supplies an observed retail price, margin is knowable
    again — the flag clears and the real number is scored."""
    confirmed = make_product(price_usd=29.99, cost_usd=4.00, price_is_derived=False)
    assert scoring.score_product(confirmed, 1000, None).margin_score > 90


# ── demand is ranked within a source, not across sources ────────────────────
# Sources count different things. On the live catalogue the median orders_count
# was 2100 for 1688 and 31 for TikTok — a 68x gap describing what the platforms
# count, not which products sell. One absolute curve let wholesale volumes take
# the entire leaderboard.
WHOLESALE = sorted([20, 50, 100, 300, 500, 800, 1200, 1800, 2100, 2600,
                    3200, 4000, 5000, 6500, 8000, 10000, 15000, 22000,
                    40000, 100000])
RETAIL = sorted([0, 1, 2, 3, 5, 7, 9, 12, 15, 18, 22, 27, 31, 38, 46,
                 60, 85, 140, 400, 167972])


def test_top_seller_on_each_platform_scores_alike():
    """A platform's best product should rank near the top of its own
    population, whatever absolute number that platform happens to print."""
    top_wholesale = scoring.demand_score(100000, WHOLESALE)
    top_retail = scoring.demand_score(167972, RETAIL)
    assert top_wholesale > 90 and top_retail > 90
    assert abs(top_wholesale - top_retail) <= 5


def test_median_of_each_platform_lands_mid_scale():
    """Whatever the platform's units, its middle product scores mid-scale."""
    for baseline in (WHOLESALE, RETAIL):
        median = baseline[len(baseline) // 2]
        assert 40 <= scoring.demand_score(median, baseline) <= 60


def test_absolute_volume_no_longer_decides_across_sources():
    """The regression: a mediocre wholesale listing outscoring a strong retail
    one purely because wholesale counts are bigger."""
    mediocre_wholesale = scoring.demand_score(2100, WHOLESALE)
    strong_retail = scoring.demand_score(400, RETAIL)
    assert strong_retail > mediocre_wholesale
    # ...whereas the absolute curve gets it backwards.
    assert scoring.demand_score(2100) > scoring.demand_score(400)


def test_ranking_is_monotonic_within_a_source():
    scores = [scoring.demand_score(n, WHOLESALE) for n in (20, 500, 2100, 10000, 100000)]
    assert scores == sorted(scores)


def test_thin_baseline_falls_back_to_the_absolute_curve():
    """Under DEMAND_MIN_CORPUS a distribution can't be read; guessing from
    four data points would be worse than the curve."""
    thin = [10, 20, 30, 40]
    assert len(thin) < scoring.DEMAND_MIN_CORPUS
    assert scoring.demand_score(5000, thin) == scoring.demand_score(5000)


def test_no_baseline_behaves_exactly_as_before():
    for n in (1, 100, 1_000, 10_000):
        assert scoring.demand_score(n, None) == scoring.demand_score(n)


def test_unknown_and_zero_keep_their_meaning_under_ranking():
    assert scoring.demand_score(None, WHOLESALE) == scoring.UNKNOWN
    assert scoring.demand_score(0, WHOLESALE) == 0


def test_uniform_population_scores_midpoint_not_ceiling():
    """Ties split. If every product sold 100 units, none of them is a winner."""
    flat = [100] * 40
    assert scoring.demand_score(100, flat) == 50


def test_percentile_rank_handles_the_edges():
    assert scoring.percentile_rank(1, []) == 0.5
    assert scoring.percentile_rank(0, [10, 20, 30]) == 0.0
    assert scoring.percentile_rank(99, [10, 20, 30]) == 1.0


def test_score_product_threads_the_baseline_through():
    product = make_product(source="tiktok", price_usd=29.99, cost_usd=None)
    ranked = scoring.score_product(product, orders_count=400,
                                   demand_baseline=RETAIL)
    absolute = scoring.score_product(product, orders_count=400)
    assert ranked.demand_score > absolute.demand_score
