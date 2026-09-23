"""Product scoring from 1688 signals.

Every component is 0-100 where HIGH is good for a dropshipper:

- demand      — units sold on 1688 (log scale) plus repurchase rate
- margin      — resale headroom from unit cost: cheap items leave room to mark up
- trend       — sales growth between daily snapshots; neutral 50 until there
                is history, rather than inventing a direction
- competition — inverted ad volume; neutral 50 with no ad data

Weights are deliberately explicit so they are easy to tune later.
"""
import math
from dataclasses import dataclass
from datetime import date

from .schemas import AdSignal, Score

WEIGHTS = {
    "demand": 0.35,
    "margin": 0.25,
    "trend": 0.25,
    "competition": 0.15,
}

NEUTRAL = 50


@dataclass(frozen=True)
class Signals:
    sales_count: int | None
    repurchase_rate: float | None       # 0.12 = 12%
    cost_usd: float | None
    snapshots: list[tuple[date, int]]   # (day, cumulative sales), any order
    ad_signals: list[AdSignal]
    location: str | None = None


def _clamp(value: float) -> int:
    return max(0, min(100, round(value)))


def demand_score(sales_count: int | None, repurchase_rate: float | None) -> int:
    """80% sales volume, 20% repurchase.

    Volume is log-scaled: 100 sold -> 40, 1k -> 60, 10k -> 80, 100k+ -> 100.
    A 30%+ repurchase rate maxes the repurchase part.
    """
    volume = 20 * math.log10(sales_count + 1) if sales_count and sales_count > 0 else 0
    repurchase = min(1.0, (repurchase_rate or 0) / 0.30) * 100
    return _clamp(min(100, volume) * 0.8 + repurchase * 0.2)


def margin_score(cost_usd: float | None) -> int:
    """$2 or less -> 100, $40 or more -> 0, log-linear between."""
    if cost_usd is None or cost_usd <= 0:
        return 0
    lo, hi = math.log10(2), math.log10(40)
    return _clamp(100 - (math.log10(cost_usd) - lo) / (hi - lo) * 100)


def trend_score(snapshots: list[tuple[date, int]]) -> int:
    """Weekly sales growth between the oldest and newest snapshot.

    0% growth -> 50, +20%/week or more -> 100, shrinking counts -> below 50.
    Needs two snapshots at least a day apart; otherwise neutral.
    """
    points = sorted((d, s) for d, s in snapshots if s is not None)
    if len(points) < 2:
        return NEUTRAL
    (first_day, first), (last_day, last) = points[0], points[-1]
    days = (last_day - first_day).days
    if days < 1 or first <= 0:
        return NEUTRAL
    weekly_growth = (last - first) / first / days * 7
    return _clamp(NEUTRAL + weekly_growth * 250)


def competition_score(ad_signals: list[AdSignal]) -> int:
    """Few advertisers scores high; 200+ ads is treated as fully saturated."""
    total_ads = sum(a.ad_count for a in ad_signals)
    if total_ads <= 0:
        return NEUTRAL  # unknown — don't claim an open market
    return _clamp(100 - (min(total_ads, 200) / 200) * 100)


def overall_score(demand: int, margin: int, competition: int, trend: int) -> int:
    return round(
        demand * WEIGHTS["demand"]
        + margin * WEIGHTS["margin"]
        + trend * WEIGHTS["trend"]
        + competition * WEIGHTS["competition"]
    )


def summary(s: Signals) -> str:
    """Plain factual one-liner; the frontend shows it where an AI blurb would go."""
    parts: list[str] = []
    if s.sales_count:
        parts.append(f"{s.sales_count:,}+ sold on 1688")
    if s.repurchase_rate:
        parts.append(f"{s.repurchase_rate:.0%} repurchase rate")
    if s.cost_usd:
        parts.append(f"${s.cost_usd:.2f} unit cost")
    if s.location:
        parts.append(f"ships from {s.location}")
    return " · ".join(parts)


def score(s: Signals) -> Score:
    demand = demand_score(s.sales_count, s.repurchase_rate)
    margin = margin_score(s.cost_usd)
    trend = trend_score(s.snapshots)
    competition = competition_score(s.ad_signals)
    return Score(
        overall_score=overall_score(demand, margin, competition, trend),
        demand_score=demand,
        margin_score=margin,
        competition_score=competition,
        trend_score=trend,
        ai_summary=summary(s),
    )
