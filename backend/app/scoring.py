"""Product scoring.

Four components, each derived from data we actually hold. The one worth
understanding is `trend_score`: it is computed from our own snapshot history
rather than bought from a provider, so it only becomes meaningful once the
ingestion worker has been running long enough to have a comparison point.

Weights are explicit so they are easy to tune.
"""
import math

from .schemas import AdSignal, Product, Score

WEIGHTS = {
    "demand": 0.30,
    "margin": 0.30,
    "trend": 0.25,
    "competition": 0.15,
}

# Neutral value for a signal we have no data for. Deliberately not 100 —
# "unknown" must never rank a product above one with proven numbers.
UNKNOWN = 50

# Units sold at which demand saturates (log scale).
DEMAND_CEILING = 10_000
# Week-over-week growth that counts as a maximum trend signal.
TREND_CEILING = 0.50


def margin_score(price_usd: float | None, cost_usd: float | None) -> int:
    """0-100 from gross margin. 70%+ margin saturates at 100."""
    if not price_usd or cost_usd is None or price_usd <= 0 or cost_usd < 0:
        return 0
    margin = (price_usd - cost_usd) / price_usd
    if margin <= 0:
        return 0
    return max(0, min(100, round(margin / 0.70 * 100)))


def demand_score(orders_count: int | None) -> int:
    """0-100 from units sold, log-scaled so the top end doesn't dominate."""
    if orders_count is None:
        return UNKNOWN
    if orders_count <= 0:
        return 0
    scaled = math.log10(orders_count + 1) / math.log10(DEMAND_CEILING + 1)
    return max(0, min(100, round(scaled * 100)))


def competition_score(ad_signals: list[AdSignal]) -> int:
    """0-100 where HIGH is good (little competition).

    Few advertisers scores high; a saturated product with many ads scores low.
    200+ ads is treated as fully saturated.
    """
    total_ads = sum(a.ad_count for a in ad_signals)
    if total_ads <= 0:
        return UNKNOWN
    return max(0, min(100, round(100 - (min(total_ads, 200) / 200) * 100)))


def trend_score(current_orders: int | None, previous_orders: int | None) -> int:
    """0-100 from order velocity between two snapshots.

    Flat demand sits at the neutral midpoint, decline pulls below it, and
    growth of TREND_CEILING over the window reaches 100. With no prior
    snapshot there is no velocity to measure, so it returns UNKNOWN.
    """
    if current_orders is None or previous_orders is None:
        return UNKNOWN
    if previous_orders <= 0:
        # Going from no recorded sales to any sales is a real signal, but the
        # ratio is undefined — treat it as moderate growth rather than infinite.
        return 75 if current_orders > 0 else UNKNOWN

    growth = (current_orders - previous_orders) / previous_orders
    return max(0, min(100, round(UNKNOWN + (growth / TREND_CEILING) * UNKNOWN)))


def overall_score(demand: int, margin: int, competition: int, trend: int) -> int:
    return round(
        demand * WEIGHTS["demand"]
        + margin * WEIGHTS["margin"]
        + trend * WEIGHTS["trend"]
        + competition * WEIGHTS["competition"]
    )


def score_product(
    product: Product,
    orders_count: int | None = None,
    previous_orders: int | None = None,
) -> Score:
    """Compute all four components plus the weighted overall.

    `previous_orders` comes from the snapshot taken ~TREND_WINDOW_DAYS ago;
    passing None simply leaves trend at the neutral midpoint.
    """
    demand = demand_score(orders_count)
    margin = margin_score(product.price_usd, product.cost_usd)
    competition = competition_score(product.ad_signals)
    trend = trend_score(orders_count, previous_orders)

    return Score(
        overall_score=overall_score(demand, margin, competition, trend),
        demand_score=demand,
        margin_score=margin,
        competition_score=competition,
        trend_score=trend,
        ai_summary=product.score.ai_summary if product.score else "",
    )
