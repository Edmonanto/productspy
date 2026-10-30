"""
Winning-product opportunity score (0-100) — eight criteria, evidence for each.

    Demand & trend momentum       20  stores advertising it, creators, views, how long ads keep
                                      running, new creatives (recent vs. older), time series
    Profitability & unit economics 20 contribution margin after product, shipping, fees,
                                      returns (economics.py), price band, markup
    Competition & saturation      15  number of stores: 3-15 = validated but open; 1 = unproven;
                                      30+ = crowded. Competition is not punished per se.
    Advertising & creative         10  AI-assessed "wow", problem solved, 3-second demo +
                                      observed engagement / share rate
    Differentiation & offer        10  AI-assessed bundle/upsell and branding potential
    Logistics & operational risk   10  fragile/heavy (AI-assessed), shipping cost vs. price
    Target market fit              10  stores advertising it IN this market, local price found
    Risk & sustainability           5  IP look-alike, seasonality, declining trend

Weights are central (CRITERIA, overridable with WINNERS_WEIGHTS) and always
re-normalised to 100.

Honesty rules:
  * Every criterion lists its evidence, each item tagged "observed" (from an ad
    or video we collected), "calculated" (deterministic maths on observed data
    + labelled assumptions), "ai" (an AI judgement) or "assumption".
  * Missing data never counts as zero and is never invented. A criterion with
    no data is left out ("known": False) and the total is the known criteria
    scaled to 100 — but at least KNOWN_FLOOR points must be known before the
    full scale-up, so one strong signal alone can't produce a high score.
  * A product seen on one platform only is capped at SINGLE_SOURCE_CAP.
  * Views are never treated as sales, nor engagement as purchase intent.
  * Confidence (high / medium / low) says how complete the evidence is; a
    "winner" needs medium or high confidence.

Interpretation (decision support, not proof of success):
  85-100 exceptional research candidate · 70-84 strong, worth validating ·
  55-69 promising, needs investigation · 40-54 weak / uncertain · <40 low priority.
Tiers: winner >= 70 (medium/high confidence) · rising >= 55 · watch >= 40.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict, fields
from datetime import datetime, timezone
from statistics import median
from typing import Iterable, Optional

from .collectors.base import AdRecord
from .economics import DEFAULTS as ECON_DEFAULTS, for_product

# ── central configuration ────────────────────────────────────────────────────
CRITERIA_DEFAULT = {
    "demand": 20, "profitability": 20, "competition": 15, "creative": 10,
    "differentiation": 10, "logistics": 10, "market_fit": 10, "risk": 5,
}
CRITERIA_LABEL = {
    "demand": "Demand & trend momentum", "profitability": "Profitability & unit economics",
    "competition": "Competition & saturation", "creative": "Advertising & creative potential",
    "differentiation": "Differentiation & offer potential", "logistics": "Logistics & operational risk",
    "market_fit": "Target market fit", "risk": "Risk & sustainability",
}


def load_weights(raw: str | None = None) -> dict[str, float]:
    """CRITERIA_DEFAULT, optionally overridden by WINNERS_WEIGHTS='{"demand": 25, ...}', scaled to 100."""
    w = dict(CRITERIA_DEFAULT)
    raw = raw if raw is not None else os.environ.get("WINNERS_WEIGHTS", "")
    if raw:
        try:
            for k, v in json.loads(raw).items():
                if k in w and float(v) >= 0:
                    w[k] = float(v)
        except (ValueError, AttributeError, TypeError):
            pass
    total = sum(w.values()) or 1
    return {k: v * 100 / total for k, v in w.items()}


CRITERIA = load_weights()
PILLARS = CRITERIA                     # kept name for older imports

WINNER_THRESHOLD = 70
RISING_THRESHOLD = 55
WATCH_FLOOR = 40
MAX_PICKS = 10
MIN_PICKS = 5
REPICK_COOLDOWN_DAYS = 30
KNOWN_FLOOR = 50          # points of criteria that must be known before full scale-up
SINGLE_SOURCE_CAP = 85    # max score for a product seen on one platform only
# A single store whose ads have run for half a year with nothing new is a
# store's long-running catalog item, not a product that is winning now.
EVERGREEN_DAYS = 180
EVERGREEN_PENALTY = 12
OLD_SINGLE_STORE_DAYS = 365
OLD_SINGLE_STORE_PENALTY = 6
WINNER_MIN_STORES = 2     # "winner" needs proof from 2+ stores (or 3+ creators); else "rising" at best

BANDS = [(85, "Exceptional research candidate"), (70, "Strong candidate worth validating"),
         (55, "Promising — needs further investigation"), (40, "Weak or uncertain opportunity"),
         (0, "Low priority on current evidence")]


def band(total: int) -> str:
    return next(label for floor, label in BANDS if total >= floor)


@dataclass
class Signals:
    # paid — Meta
    meta_ads: int = 0
    max_days_running: Optional[int] = None
    median_days_running: Optional[int] = None
    creatives: int = 0
    new_creatives_7d: int = 0
    new_creatives_14d: int = 0
    new_creatives_30d: int = 0
    reach_total: Optional[int] = None
    # paid — TikTok
    tiktok_ads: int = 0
    best_ctr: Optional[float] = None
    max_budget_level: Optional[int] = None
    # paid — both
    advertisers: int = 0
    # organic
    videos: int = 0
    recent_videos_14d: int = 0
    creators: int = 0
    total_views: Optional[int] = None
    engagement_rate: Optional[float] = None
    share_ratio: Optional[float] = None
    intent_ratio: Optional[float] = None
    views_per_hour: Optional[float] = None
    # time series: active paid ads on earlier scans (oldest first), from winner_scores
    paid_ads_history: list = field(default_factory=list)
    # Google Trends (trends.py): status rising|stable|falling|spike|low|no_data
    search_status: Optional[str] = None
    search_growth: Optional[float] = None
    search_level: Optional[float] = None
    search_term: Optional[str] = None
    search_geo: Optional[str] = None
    # product
    first_seen_days: Optional[int] = None
    sell_price_usd: Optional[float] = None
    cost_usd: Optional[float] = None
    cost_estimated: bool = False
    wow: Optional[float] = None
    problem: Optional[float] = None
    demo3s: Optional[bool] = None
    upsell: Optional[float] = None
    brandable: Optional[float] = None
    ip_risk: Optional[str] = None
    restricted: bool = False
    fragile_heavy: Optional[bool] = None
    seasonal: Optional[bool] = None
    physical: bool = True
    last_picked_days_ago: Optional[int] = None

    @property
    def sources(self) -> list[str]:
        s = []
        if self.meta_ads:
            s.append("facebook_ads")
        if self.tiktok_ads:
            s.append("tiktok_ads")
        if self.videos:
            s.append("tiktok_organic")
        return s


@dataclass
class ScoreResult:
    total: int
    breakdown: dict
    penalties: list = field(default_factory=list)
    reasons: list = field(default_factory=list)
    confidence: str = "low"
    excluded: Optional[str] = None
    signals: dict = field(default_factory=dict)


# ── aggregation ──────────────────────────────────────────────────────────────
def _days(now: datetime, d: Optional[datetime]) -> Optional[int]:
    if not d:
        return None
    return max(0, (now - d).days)


def aggregate(ads: Iterable[AdRecord], now: Optional[datetime] = None, **product_fields) -> Signals:
    now = now or datetime.now(timezone.utc)
    ads = list(ads)
    meta = [a for a in ads if a.platform == "meta" and a.is_active]
    tta = [a for a in ads if a.platform == "tiktok_ads"]
    org = [a for a in ads if a.platform == "tiktok_organic"]
    paid = meta + tta
    names = {f.name for f in fields(Signals)}
    s = Signals(**{k: v for k, v in product_fields.items() if k in names})

    s.meta_ads = len(meta)
    run_days = [d for d in (_days(now, a.started_at) for a in meta) if d is not None]
    if run_days:
        s.max_days_running = max(run_days)
        s.median_days_running = int(median(run_days))
    s.creatives = sum(max(1, a.variant_count or 1) for a in meta) + len(tta)
    ages = [d for d in (_days(now, a.started_at) for a in paid) if d is not None]
    s.new_creatives_7d = sum(1 for d in ages if d <= 7)
    s.new_creatives_14d = sum(1 for d in ages if d <= 14)
    s.new_creatives_30d = sum(1 for d in ages if d <= 30)
    reach = [a.reach for a in meta if a.reach]
    s.reach_total = sum(reach) if reach else None

    s.tiktok_ads = len(tta)
    ctrs = [a.ctr for a in tta if a.ctr]
    s.best_ctr = max(ctrs) if ctrs else None
    budgets = [a.budget_level for a in tta if a.budget_level]
    s.max_budget_level = max(budgets) if budgets else None

    stores = {(a.landing_domain or (a.advertiser_id or a.advertiser_name or "").lower()) for a in paid}
    stores.discard("")
    s.advertisers = len(stores)

    s.videos = len(org)
    s.recent_videos_14d = sum(1 for a in org if (d := _days(now, a.started_at)) is not None and d <= 14)
    s.creators = len({(a.advertiser_id or a.advertiser_name) for a in org if (a.advertiser_id or a.advertiser_name)})
    views = sum(a.views or 0 for a in org)
    if views:
        s.total_views = views
        inter = sum((a.likes or 0) + (a.comments or 0) + (a.shares or 0) for a in org)
        s.engagement_rate = inter / views
    likes = sum(a.likes or 0 for a in org) + sum(a.likes or 0 for a in tta)
    shares = sum(a.shares or 0 for a in org) + sum(a.shares or 0 for a in tta)
    if likes:
        s.share_ratio = shares / likes
    sampled = sum(a.sampled_comments or 0 for a in org)
    if sampled >= 20:
        s.intent_ratio = sum(a.intent_comments or 0 for a in org) / sampled
    vph = []
    for a in org:
        if a.started_at and a.views:
            hours = max(1.0, (now - a.started_at).total_seconds() / 3600)
            if hours <= 24 * 7:
                vph.append(a.views / hours)
    s.views_per_hour = max(vph) if vph else None

    starts = [a.started_at for a in ads if a.started_at]
    if starts and s.first_seen_days is None:
        s.first_seen_days = _days(now, min(starts))
    return s


# ── trend status ─────────────────────────────────────────────────────────────
def trend_status(s: Signals) -> tuple[str, str]:
    """(status, explanation). Status: emerging | growing | stable | declining | seasonal | spike | unknown."""
    paid_now = s.meta_ads + s.tiktok_ads
    hist = [h for h in s.paid_ads_history if isinstance(h, (int, float))]
    if s.seasonal:
        return "seasonal", "AI flags it as seasonal — demand depends on the time of year"
    q = f"Google searches for “{s.search_term}”" if s.search_term else "Google searches"
    if s.search_status == "spike":
        return "spike", f"{q} jumped far above their usual level in the last few weeks — may be a short viral burst"
    if len(hist) >= 3:
        window = hist[-7:]                 # earlier scans only (today is paid_now)
        earlier = sum(window) / len(window)
        if earlier >= 3 and paid_now <= earlier * 0.6:
            return "declining", f"Active ads fell from ~{earlier:.0f} to {paid_now} over recent scans"
        if earlier >= 1 and paid_now >= earlier * 1.4 and paid_now - earlier >= 2:
            return "growing", f"Active ads rose from ~{earlier:.0f} to {paid_now} over recent scans"
    if s.search_status == "rising":
        return "growing", f"{q} up {round((s.search_growth or 1) * 100 - 100)}% over the last 4 weeks vs the 8 before"
    total = s.creatives or paid_now
    if s.first_seen_days is not None and s.first_seen_days <= 21 and (s.new_creatives_14d or s.recent_videos_14d):
        return "emerging", f"First seen {s.first_seen_days} days ago, new ads/videos still appearing"
    if total >= 3 and s.new_creatives_14d / max(1, paid_now) >= 0.3:
        return "growing", f"{s.new_creatives_14d} of {paid_now} active ads launched in the last 14 days"
    if s.views_per_hour and s.views_per_hour >= 2000 and s.recent_videos_14d:
        return "growing", f"Recent videos gaining ~{int(s.views_per_hour):,} views/hour"
    if s.max_days_running and s.max_days_running >= 30 and paid_now:
        if s.new_creatives_30d == 0:
            return "stable", f"Ads running up to {s.max_days_running} days, no new ads in 30 days (mature)"
        return "stable", f"Ads running up to {s.max_days_running} days and still being refreshed"
    if s.search_status == "falling":
        return "declining", f"{q} down {round(100 - (s.search_growth or 1) * 100)}% over the last 4 weeks vs the 8 before"
    if s.search_status == "stable" and (s.search_level or 0) >= 10:
        return "stable", f"{q} steady over the last 3 months"
    return "unknown", "Not enough dated evidence to tell the direction yet"


# ── scoring helpers ──────────────────────────────────────────────────────────
def _tier(value, table: list[tuple[float, float]]) -> float:
    """table = [(threshold, points), ...] highest threshold first."""
    for threshold, pts in table:
        if value >= threshold:
            return pts
    return 0.0


class _C:
    """One criterion: sub-signals (earned or None, max) + evidence."""

    def __init__(self) -> None:
        self.parts: list[tuple[Optional[float], float]] = []
        self.evidence: list[dict] = []

    def add(self, earned: Optional[float], sub_max: float) -> None:
        self.parts.append((earned, sub_max))

    def ev(self, text: str, kind: str = "observed") -> None:
        self.evidence.append({"text": text, "kind": kind})

    def ratio(self) -> tuple[Optional[float], float]:
        """(0-1 score or None if nothing known, coverage). Thin coverage is capped at 0.6."""
        full = sum(m for _, m in self.parts) or 1
        known = [(e, m) for e, m in self.parts if e is not None]
        avail = sum(m for _, m in known)
        if avail == 0:
            return None, 0.0
        cov = avail / full
        r = sum(e for e, _ in known) / avail
        if cov < 0.4:
            r = min(r, 0.6)
        return r, cov


def score(s: Signals, weights: Optional[dict[str, float]] = None) -> ScoreResult:
    W = weights or CRITERIA
    C = {k: _C() for k in CRITERIA_DEFAULT}
    paid_now = s.meta_ads + s.tiktok_ads

    # ---------- hard filters
    excluded = None
    if not s.physical:
        excluded = "not a physical product"
    elif s.restricted:
        excluded = "restricted category"
    elif s.ip_risk == "high":
        excluded = "brand / IP copy risk"
    elif s.last_picked_days_ago is not None and s.last_picked_days_ago < REPICK_COOLDOWN_DAYS:
        excluded = f"already picked {s.last_picked_days_ago} days ago"

    trend, trend_why = trend_status(s)

    # ---------- A. demand & trend momentum
    c = C["demand"]
    if s.advertisers:
        c.add(_tier(s.advertisers, [(5, 6), (3, 5), (2, 3), (1, 1.5)]), 6)
        c.ev(f"{s.advertisers} different stores running ads for it" if s.advertisers > 1
             else "1 store running ads for it")
    else:
        c.add(None, 6)
    if s.max_days_running is not None:
        d = s.max_days_running
        # Long-running proves it sells; past ~4 months it says "established", not "trending now".
        c.add(2.0 if d > 365 else 3.5 if d > 120 else _tier(d, [(30, 5), (14, 4), (7, 2.5), (4, 1)]), 5)
        if d > 365:
            c.ev(f"Ads running for {d} days — an established product, not a new trend")
        elif d > 120:
            c.ev(f"An ad running for {d} days — proven, but no longer new")
        elif d >= 7:
            c.ev(f"An ad still running after {d} days — advertisers keep paying for it")
    else:
        c.add(None, 5)
    if paid_now:
        c.add(_tier(s.new_creatives_14d, [(5, 4), (2, 3), (1, 1.5)]), 4)
        if s.new_creatives_14d:
            c.ev(f"{s.new_creatives_14d} new ad{'s' if s.new_creatives_14d > 1 else ''} launched in the last 14 days")
    else:
        c.add(None, 4)
    if s.videos:
        c.add(_tier(s.creators, [(10, 3), (5, 2.5), (3, 1.5), (1, 0.5)]), 3)
        c.ev(f"{s.creators} creator{'s' if s.creators != 1 else ''} posted about it"
             + (f" ({s.total_views:,} lifetime views — views are not sales)" if s.total_views else ""))
    else:
        c.add(None, 3)
    if s.views_per_hour is not None:
        c.add(_tier(s.views_per_hour, [(10_000, 2), (2_000, 1.5), (500, 0.5)]), 2)
        if s.views_per_hour >= 2000:
            c.ev(f"A video from the last 7 days is gaining ~{int(s.views_per_hour):,} views/hour")
    else:
        c.add(None, 2)
    if s.search_status:
        where = f" in {s.search_geo}" if s.search_geo else ""
        if s.search_status == "no_data":
            c.add(None, 4)
        else:
            pts = {"rising": 4.0, "spike": 2.5, "falling": 0.5, "low": 0.5}.get(
                s.search_status, 3.0 if (s.search_level or 0) >= 25 else 2.0)
            c.add(pts, 4)
            c.ev({"rising": f"Google searches rising{where}: {round((s.search_growth or 1) * 100 - 100)}% up in the last 4 weeks",
                  "spike": f"Google searches spiked recently{where} — check it lasts before scaling",
                  "falling": f"Google searches falling{where} ({round(100 - (s.search_growth or 1) * 100)}% down vs the 8 weeks before)",
                  "low": f"Very little Google search interest{where} for “{s.search_term}”",
                  }.get(s.search_status, f"Google searches steady{where} (index {s.search_level:.0f}/100)")
                 + " — Google Trends index, not sales", "observed")
    if trend == "declining":
        c.parts.append((0.0, 2))
        c.ev(trend_why, "calculated")
    elif trend in ("growing", "emerging"):
        c.ev(f"Trend {trend}: {trend_why}", "calculated")

    # ---------- B. profitability & unit economics
    c = C["profitability"]
    econ = for_product(s.sell_price_usd, s.cost_usd)
    if econ.complete:
        cm = econ.contribution_margin_pct or 0
        pts = _tier(cm, [(50, 12), (40, 9.5), (30, 7), (20, 4), (10, 1.5)])
        if s.cost_estimated:
            pts *= 0.85
        c.add(pts, 12)
        c.ev(f"Contribution before ads ≈ ${econ.contribution_before_ads_usd:.2f} per order "
             f"({cm:.0f}% of the ${s.sell_price_usd:.2f} price) after cost, shipping, fees and returns",
             "calculated")
        c.ev(f"Break-even ROAS {econ.break_even_roas:.2f} (max ad spend ${econ.break_even_cpa_usd:.2f} per order)"
             if econ.break_even_roas else "No room for ad spend at this price", "calculated")
        c.ev("Product cost is an AI estimate — confirm with a supplier quote" if s.cost_estimated
             else f"Product cost ${s.cost_usd:.2f} from a supplier listing",
             "ai" if s.cost_estimated else "observed")
        c.ev("Assumes $5 shipping, $0.50 packaging, 3% + $0.30 fees, 5% returns", "assumption")
        c.add(_tier(econ.markup or 0, [(4, 4), (3, 3), (2.5, 2), (2, 1)]), 4)
    else:
        c.add(None, 12)
        c.add(None, 4)
    if s.sell_price_usd and econ.complete:
        p = s.sell_price_usd
        c.add(4.0 if 20 <= p <= 60 else 2.5 if (15 <= p < 20 or 60 < p <= 90) else 1.0, 4)
        c.ev(f"Competitors sell it at ${p:.2f}" + (" — in the $20-60 impulse-buy range" if 20 <= p <= 60 else ""))
    else:
        # Profitability needs both a price and a cost; a price alone is not scored.
        c.add(None, 4)
        if s.sell_price_usd:
            c.ev(f"Competitors sell it at ${s.sell_price_usd:.2f}, but no product cost was found — "
                 "profitability not scored until you add a supplier cost")

    # ---------- C. competition & saturation
    c = C["competition"]
    if s.advertisers:
        n = s.advertisers
        pts = 15 if 3 <= n <= 15 else 11 if 16 <= n <= 30 else 9 if n == 2 else 6 if n == 1 else 4 if n <= 50 else 1.5
        c.add(pts, 15)
        c.ev({1: "Only 1 store advertising it — open, but demand is not yet proven by others",
              2: "2 stores advertising it — early, little competition"}.get(
            n, f"{n} stores advertising it — " + ("validated and not saturated" if n <= 15
                                                   else "getting crowded, needs a differentiated offer" if n <= 50
                                                   else "saturated in the ads we see")))
        if s.creatives and n:
            c.ev(f"{s.creatives} active ad creatives across those stores")
    else:
        c.add(None, 15)

    # ---------- D. advertising & creative potential
    c = C["creative"]
    if s.wow is not None:
        c.add(_tier(float(s.wow), [(8, 3), (6, 2), (4, 1)]), 3)
    else:
        c.add(None, 3)
    if s.problem is not None:
        c.add(_tier(float(s.problem), [(8, 3), (6, 2), (4, 1)]), 3)
    else:
        c.add(None, 3)
    if s.demo3s is not None:
        c.add(2.0 if s.demo3s else 0.0, 2)
    else:
        c.add(None, 2)
    if s.wow is not None or s.problem is not None:
        c.ev(f"AI rates it {s.wow or '?'}/10 scroll-stopping, {s.problem or '?'}/10 problem-solving"
             + (", benefit shown in 3 seconds" if s.demo3s else ""), "ai")
    eng = None
    if s.engagement_rate is not None:
        eng = _tier(s.engagement_rate, [(0.10, 2), (0.06, 1.5), (0.04, 1), (0.02, 0.5)])
        if s.engagement_rate >= 0.04:
            c.ev(f"{s.engagement_rate * 100:.1f}% engagement on TikTok videos (likes+comments+shares / views)")
    elif s.best_ctr is not None:
        eng = _tier(s.best_ctr, [(0.03, 2), (0.02, 1.5), (0.01, 0.5)])
        c.ev(f"{s.best_ctr * 100:.1f}% CTR on TikTok ads")
    c.add(eng, 2)
    if s.intent_ratio and s.intent_ratio >= 0.02:
        c.ev(f"{s.intent_ratio * 100:.0f}% of sampled comments ask where to buy / the price "
             "(interest, not confirmed orders)")

    # ---------- E. differentiation & offer potential
    c = C["differentiation"]
    c.add(_tier(float(s.upsell), [(8, 5), (6, 3.5), (4, 2)]) if s.upsell is not None else None, 5)
    c.add(_tier(float(s.brandable), [(8, 5), (6, 3.5), (4, 2)]) if s.brandable is not None else None, 5)
    if s.upsell is not None or s.brandable is not None:
        c.ev(f"AI rates bundle/upsell potential {s.upsell if s.upsell is not None else '?'}/10, "
             f"branding potential {s.brandable if s.brandable is not None else '?'}/10", "ai")

    # ---------- F. logistics & operational risk
    c = C["logistics"]
    if s.fragile_heavy is not None:
        c.add(0.0 if s.fragile_heavy else 5.0, 5)
        c.ev("AI flags it as fragile, liquid or heavy — shipping/damage risk" if s.fragile_heavy
             else "Small and robust to ship (AI-assessed)", "ai")
    else:
        c.add(None, 5)
    if s.sell_price_usd:
        ratio = ECON_DEFAULTS["shipping_usd"] / s.sell_price_usd
        c.add(_tier(-ratio, [(-0.10, 5), (-0.20, 3), (-0.30, 1)]), 5)
        c.ev(f"Assumed $5 shipping is {ratio * 100:.0f}% of the selling price", "calculated")
    else:
        c.add(None, 5)

    # ---------- G. target market fit (the data is collected per market)
    c = C["market_fit"]
    if paid_now:
        c.add(_tier(s.advertisers, [(3, 6), (2, 4), (1, 2.5)]), 6)
        c.ev(f"Advertised to shoppers in this market ({s.advertisers} store{'s' if s.advertisers != 1 else ''})")
    else:
        c.add(None, 6)
    if s.sell_price_usd:
        c.add(4.0, 4)
        c.ev("A selling price was found on a store advertising in this market")
    else:
        c.add(None, 4)

    # ---------- H. risk & sustainability
    c = C["risk"]
    if s.ip_risk is not None:
        c.add(0.0 if s.ip_risk == "low" else 2.0, 2)
        if s.ip_risk == "low":
            c.ev("Possible brand look-alike — check IP before selling", "ai")
    else:
        c.add(None, 2)
    if s.seasonal is not None:
        c.add(0.0 if s.seasonal else 1.5, 1.5)
        if s.seasonal:
            c.ev("Seasonal demand", "ai")
    else:
        c.add(None, 1.5)
    if trend != "unknown":
        c.add(0.0 if trend == "declining" else 0.75 if trend == "spike" else 1.5, 1.5)
        if trend == "spike":
            c.ev("Search interest is a recent spike — may fade quickly", "observed")
        if trend == "declining":
            c.ev("Advertising for it is declining", "calculated")
    else:
        c.add(None, 1.5)
    if not c.evidence and any(e is not None for e, _ in c.parts):
        if s.ip_risk is not None or s.seasonal is not None:
            c.ev("No brand look-alike, seasonality or decline flags found", "ai")
        else:
            c.ev("Advertising for it is not declining — IP and seasonality not assessed yet", "calculated")

    # ---------- totals
    criteria, breakdown = {}, {}
    for k, crit in C.items():
        r, cov = crit.ratio()
        pts = None if r is None else round(r * W[k], 1)
        breakdown[k] = pts
        criteria[k] = {"score": pts, "max": round(W[k], 1), "known": r is not None,
                       "coverage": round(cov, 2), "evidence": crit.evidence}
    known_max = sum(W[k] for k, v in breakdown.items() if v is not None)
    earned = sum(v for v in breakdown.values() if v is not None)
    raw = 100 * earned / max(known_max, KNOWN_FLOOR) if known_max else 0.0
    n_src = len(s.sources)
    capped = n_src <= 1 and raw > SINGLE_SOURCE_CAP
    if capped:
        raw = SINGLE_SOURCE_CAP
    total = int(round(max(0, min(100, raw))))

    # ---------- penalties: patterns the criteria above can't see on their own
    penalties = []
    single = s.advertisers <= 1 and (s.meta_ads + s.tiktok_ads) > 0
    if single and s.max_days_running is not None:
        if s.max_days_running >= EVERGREEN_DAYS and s.new_creatives_30d == 0:
            penalties.append({"points": -EVERGREEN_PENALTY, "reason":
                              f"Only 1 store, ads running {s.max_days_running} days with no new ads in 30 days "
                              "— looks like a store's long-running catalog ad, not a product winning now"})
        elif s.max_days_running >= OLD_SINGLE_STORE_DAYS:
            penalties.append({"points": -OLD_SINGLE_STORE_PENALTY, "reason":
                              f"Only 1 store, advertising it for {s.max_days_running} days — "
                              "one brand's established product, not yet copied by others"})
    total = max(0, total + sum(p["points"] for p in penalties))

    confidence = ("high" if n_src >= 2 and known_max >= 75
                  else "medium" if n_src >= 2 or known_max >= 70 else "low")

    strengths, weaknesses = [], []
    for k, info in criteria.items():
        if info["score"] is None or not info["evidence"]:
            continue
        ratio = info["score"] / info["max"] if info["max"] else 0
        if ratio >= 0.7:
            text = info["evidence"][0]["text"]
            # Demand and competition both start from the store count: say it once.
            if k == "competition" and any("store" in t and t.split()[0] == text.split()[0] for t in strengths):
                text = next((e["text"] for e in info["evidence"][1:]), None)
            if text:
                strengths.append(text)
        elif ratio < 0.4:
            weaknesses.append(info["evidence"][0]["text"])
    missing = [k for k, v in breakdown.items() if v is None]
    if capped:
        weaknesses.append("Seen on one platform only — score capped until confirmed elsewhere")
    weaknesses = [p["reason"] for p in penalties] + weaknesses

    sig = asdict(s)
    sig.update({
        "known_points": round(known_max, 1), "missing_pillars": missing, "criteria": criteria,
        "trend": trend, "trend_why": trend_why, "band": band(total),
        "strengths": strengths[:6], "weaknesses": weaknesses[:6],
        "economics": asdict(econ),
    })
    return ScoreResult(
        total=total, breakdown=breakdown, penalties=penalties, reasons=strengths[:7],
        confidence=confidence, excluded=excluded, signals=sig,
    )


# ── selection ────────────────────────────────────────────────────────────────
def pick_winners(scored: list[tuple[str, ScoreResult]], max_picks: int = MAX_PICKS,
                 min_picks: int = MIN_PICKS) -> list[tuple[str, ScoreResult, str]]:
    """scored = [(product_id, result)]. Returns [(product_id, result, tier)] ranked."""
    eligible = sorted((x for x in scored if not x[1].excluded),
                      key=lambda x: (x[1].total, x[1].confidence == "high"), reverse=True)

    def is_winner(r: ScoreResult) -> bool:
        sig = r.signals or {}
        proven = (sig.get("advertisers") or 0) >= WINNER_MIN_STORES or (sig.get("creators") or 0) >= 3
        return r.total >= WINNER_THRESHOLD and r.confidence != "low" and proven

    winners = [(pid, r, "winner") for pid, r in eligible if is_winner(r)][:max_picks]
    if len(winners) < min_picks:
        fillers = [(pid, r, "rising") for pid, r in eligible
                   if r.total >= RISING_THRESHOLD and not is_winner(r)]
        winners += fillers[: min_picks - len(winners)]
    if len(winners) < min_picks:
        watch = [(pid, r, "watch") for pid, r in eligible
                 if WATCH_FLOOR <= r.total < RISING_THRESHOLD]
        winners += watch[: min_picks - len(winners)]
    return winners
