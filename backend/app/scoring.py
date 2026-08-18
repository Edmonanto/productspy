"""Product scoring.

Phase 1 implements the parts that are deterministic from data we already
store. Demand, competition and trend need the time-series ad/order signals the
Phase 2 ingestion worker will collect — until then existing values are kept.

Weights are deliberately explicit so they are easy to tune later.
"""
from .schemas import AdSignal, Product, Score

WEIGHTS = {
    "demand": 0.30,
    "margin": 0.30,
    "trend": 0.25,
    "competition": 0.15,
}


def margin_score(price_usd: float | None, cost_usd: float | None) -> int:
    """0-100 from gross margin. 70%+ margin saturates at 100."""
    if not price_usd or not cost_usd or price_usd <= 0 or cost_usd < 0:
        return 0
    margin = (price_usd - cost_usd) / price_usd
    if margin <= 0:
        return 0
    return max(0, min(100, round(margin / 0.70 * 100)))


def competition_score(ad_signals: list[AdSignal]) -> int:
    """0-100 where HIGH is good (little competition).

    Few advertisers competing on a product scores high; a saturated product
    with many ads scores low. 200+ ads is treated as fully saturated.
    """
    total_ads = sum(a.ad_count for a in ad_signals)
    if total_ads <= 0:
        return 50  # unknown — sit at neutral rather than claiming no competition
    return max(0, min(100, round(100 - (min(total_ads, 200) / 200) * 100)))


def overall_score(demand: int, margin: int, competition: int, trend: int) -> int:
    return round(
        demand * WEIGHTS["demand"]
        + margin * WEIGHTS["margin"]
        + trend * WEIGHTS["trend"]
        + competition * WEIGHTS["competition"]
    )


def rescore(product: Product) -> Score:
    """Recompute what Phase 1 can, preserving signal-derived components."""
    previous = product.score

    demand = previous.demand_score if previous else 0
    trend = previous.trend_score if previous else 0
    summary = previous.ai_summary if previous else ""

    margin = margin_score(product.price_usd, product.cost_usd)
    competition = competition_score(product.ad_signals)

    return Score(
        overall_score=overall_score(demand, margin, competition, trend),
        demand_score=demand,
        margin_score=margin,
        competition_score=competition,
        trend_score=trend,
        ai_summary=summary,
    )
