"""Product scoring.

Four components, each derived from data we actually hold. The one worth
understanding is `trend_score`: it is computed from our own snapshot history
rather than bought from a provider, so it only becomes meaningful once the
ingestion worker has been running long enough to have a comparison point.

Weights are explicit so they are easy to tune.
"""
import bisect
import math
from typing import Sequence

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

# Units sold at which demand saturates (log scale). Only used as a fallback:
# see demand_score for why an absolute curve can't compare across sources.
DEMAND_CEILING = 10_000
# Below this many products with a known orders_count, a source's own
# distribution is too thin to read a percentile from, so the absolute curve
# stands in. Mirrors MIN_CORPUS_FOR_DF in the matcher.
DEMAND_MIN_CORPUS = 20
# Week-over-week growth that counts as a maximum trend signal.
TREND_CEILING = 0.50


def margin_score(
    price_usd: float | None,
    cost_usd: float | None,
    price_is_derived: bool = False,
) -> int:
    """0-100 from gross margin. 70%+ margin saturates at 100.

    An *unknown* margin returns the neutral midpoint, not 0. Sources differ in
    what they expose — TikTok reports retail with no supplier cost, 1688 the
    reverse — and scoring a missing input as zero margin would permanently
    bury every product from a source that simply doesn't publish that field.
    A real zero (price at or below cost) still scores 0.

    A *derived* price is the same kind of unknown. Where a source publishes no
    retail price we compute one as cost * WHOLESALE_MARKUP, which makes margin
    (m-1)/m for every such row — the config constant restated, identical across
    the catalogue and independent of the product. Scoring that as an observed
    margin handed every 1688 listing 95/100 and 30% of the composite weight,
    ranking untranslated supplier listings above real retail winners. Margin
    becomes knowable when a confirmed match supplies an observed retail price
    to go with the observed cost.
    """
    if price_is_derived:
        return UNKNOWN
    if price_usd is None or cost_usd is None or price_usd <= 0 or cost_usd < 0:
        return UNKNOWN
    margin = (price_usd - cost_usd) / price_usd
    if margin <= 0:
        return 0
    return max(0, min(100, round(margin / 0.70 * 100)))


def percentile_rank(value: int, baseline: Sequence[int]) -> float:
    """Fraction of `baseline` this value beats, counting ties as half.

    `baseline` must be sorted ascending. Ties split so that every member of a
    uniform population scores the midpoint rather than the ceiling.
    """
    n = len(baseline)
    if n == 0:
        return 0.5
    below = bisect.bisect_left(baseline, value)
    equal = bisect.bisect_right(baseline, value) - below
    return (below + equal / 2) / n


def demand_score(
    orders_count: int | None, baseline: Sequence[int] | None = None
) -> int:
    """0-100 from units sold, ranked within the product's own source.

    Sources count different things. 1688's 已售 figure is cumulative wholesale
    units across resellers on a listing that may be years old; TikTok's is
    retail units on one storefront listing. Measured on the live catalogue the
    medians were 2100 and 31 — a 68x gap that reflects what the platforms
    count, not which products sell. Put through one absolute curve, the
    wholesale number wins structurally and 1688 takes the whole leaderboard.

    So a product is ranked against its own platform's distribution: the top
    seller on TikTok and the top seller on 1688 both score near 100, which is
    the comparison that carries meaning across sources.

    Without a baseline — or with one too thin to read (DEMAND_MIN_CORPUS) —
    this falls back to the absolute log curve. A genuine zero still scores 0,
    and an unknown count still scores neutral.
    """
    if orders_count is None:
        return UNKNOWN
    if orders_count <= 0:
        return 0
    if baseline is not None and len(baseline) >= DEMAND_MIN_CORPUS:
        return max(0, min(100, round(percentile_rank(orders_count, baseline) * 100)))
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
    demand_baseline: Sequence[int] | None = None,
) -> Score:
    """Compute all four components plus the weighted overall.

    `previous_orders` comes from the snapshot taken ~TREND_WINDOW_DAYS ago;
    passing None simply leaves trend at the neutral midpoint.

    `demand_baseline` is the sorted orders_count distribution for this
    product's own source. Every caller should pass it — a manual rescore and a
    scheduled one must not disagree — but omitting it degrades to the absolute
    curve rather than failing.
    """
    demand = demand_score(orders_count, demand_baseline)
    margin = margin_score(
        product.price_usd, product.cost_usd, product.price_is_derived
    )
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
