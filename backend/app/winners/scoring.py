"""
Winning-product score (0-100).

    Scaling proof   30  advertisers keep paying for it (days running, # creatives,
                        new creatives this week, reach / budget)
    Engagement      25  engagement rate, shares, buying-intent comments, CTR
    Proven demand   20  3-15 different stores selling it, many creators, views
    Margin          15  sell price >= 3x landed cost, $20-60 sweet spot
    Freshness       10  new (not old news), views accelerating, wow / problem-solving
    Penalties           saturation (>30/50 stores), fragile/heavy, seasonal,
                        brand-IP risk, single source only
    Hard filters        restricted items, high IP risk, not a physical product,
                        already picked in the last 30 days

Missing data never counts as zero:
  * inside a pillar, the signals that are known are scaled up (capped at 60 %
    of the pillar when less than 40 % of its signals are known);
  * a pillar with no data at all (e.g. engagement for a product only seen in
    Facebook ads — likes and comments come from TikTok) is left out, and the
    total is the known pillars scaled to 100. At least KNOWN_FLOOR points of
    pillars must be known, otherwise the scale-up is limited, so one strong
    signal on its own can't produce a high score.
  * a product seen on one platform only is capped at SINGLE_SOURCE_CAP, and
    a "winner" needs medium or high confidence (two platforms, or most
    pillars known) — a low-confidence 70+ is shown as "rising".
  * breakdown values are None for pillars with no data ("no data" in the app).

Thresholds: >= 70 -> "winner". If fewer than MIN_PICKS qualify, the best
60-69 products fill up to MIN_PICKS as "rising", and if there still aren't
enough, the best of the rest (score >= WATCH_FLOOR) fill in as "watch" —
early signals with thin evidence, shown with their real score so a quiet day
or a free-data scan still gives the user something to look at.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Iterable, Optional

from .collectors.base import AdRecord

PILLARS = {"scaling": 30, "engagement": 25, "demand": 20, "margin": 15, "freshness": 10}
WINNER_THRESHOLD = 70
RISING_THRESHOLD = 60
WATCH_FLOOR = 20
MAX_PICKS = 10
MIN_PICKS = 5
REPICK_COOLDOWN_DAYS = 30
KNOWN_FLOOR = 50          # points of pillars that must be known before full scale-up
SINGLE_SOURCE_CAP = 85    # max score for a product seen on one platform only


@dataclass
class Signals:
    # paid — Meta
    meta_ads: int = 0
    max_days_running: Optional[int] = None
    median_days_running: Optional[int] = None
    creatives: int = 0
    new_creatives_7d: int = 0
    reach_total: Optional[int] = None
    # paid — TikTok
    tiktok_ads: int = 0
    best_ctr: Optional[float] = None
    max_budget_level: Optional[int] = None
    # paid — both
    advertisers: int = 0
    # organic
    videos: int = 0
    creators: int = 0
    total_views: Optional[int] = None
    engagement_rate: Optional[float] = None
    share_ratio: Optional[float] = None
    intent_ratio: Optional[float] = None
    views_per_hour: Optional[float] = None
    # product
    first_seen_days: Optional[int] = None
    sell_price_usd: Optional[float] = None
    cost_usd: Optional[float] = None
    cost_estimated: bool = False
    wow: Optional[float] = None
    problem: Optional[float] = None
    ip_risk: str = "none"
    restricted: bool = False
    fragile_heavy: bool = False
    seasonal: bool = False
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


# ------------------------------------------------------------- aggregation

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
    s = Signals(**{k: v for k, v in product_fields.items() if hasattr(Signals, k)})

    s.meta_ads = len(meta)
    run_days = [d for d in (_days(now, a.started_at) for a in meta) if d is not None]
    if run_days:
        s.max_days_running = max(run_days)
        s.median_days_running = int(median(run_days))
    s.creatives = sum(max(1, a.variant_count or 1) for a in meta) + len(tta)
    s.new_creatives_7d = sum(1 for a in paid if (d := _days(now, a.started_at)) is not None and d <= 7)
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


# ------------------------------------------------------------- scoring

def _tier(value, table: list[tuple[float, float]]) -> float:
    """table = [(threshold, points), ...] highest threshold first."""
    for threshold, pts in table:
        if value >= threshold:
            return pts
    return 0.0


def _pillar(parts: list[tuple[Optional[float], float]], pillar_max: float) -> tuple[float, float]:
    """parts = [(earned or None if unknown, sub_max)]. Returns (score, coverage)."""
    full = sum(m for _, m in parts)
    known = [(e, m) for e, m in parts if e is not None]
    avail = sum(m for _, m in known)
    if avail == 0:
        return None, 0.0
    coverage = avail / full
    score = pillar_max * sum(e for e, _ in known) / avail
    if coverage < 0.4:
        score = min(score, 0.6 * pillar_max)
    return score, coverage


def score(s: Signals) -> ScoreResult:
    reasons: list[str] = []
    penalties: list[dict] = []

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

    # ---------- 1. scaling proof (30)
    longevity = _tier(s.max_days_running, [(30, 10), (14, 8), (7, 5), (4, 2)]) if s.max_days_running is not None else None
    creatives = _tier(s.creatives, [(15, 8), (8, 6), (5, 4), (2, 2)]) if (s.meta_ads or s.tiktok_ads) else None
    fresh_cr = _tier(s.new_creatives_7d, [(5, 6), (2, 4), (1, 2)]) if (s.meta_ads or s.tiktok_ads) else None
    spend = None
    if s.reach_total:
        spend = _tier(s.reach_total, [(500_000, 6), (100_000, 4), (50_000, 2), (10_000, 1)])
    elif s.max_budget_level:
        spend = _tier(s.max_budget_level, [(4, 6), (3, 4), (2, 2)])
    scaling, cov_scaling = _pillar([(longevity, 10), (creatives, 8), (fresh_cr, 6), (spend, 6)], 30)
    if s.max_days_running and s.max_days_running >= 7:
        reasons.append(f"Ad still running after {s.max_days_running} days on Facebook/Instagram")
    if s.creatives >= 5:
        reasons.append(f"{s.creatives} active ad creatives" +
                       (f", {s.new_creatives_7d} launched this week" if s.new_creatives_7d else ""))
    if s.reach_total and s.reach_total >= 50_000:
        reasons.append(f"{s.reach_total:,} people reached by its ads (EU data)")
    if s.tiktok_ads:
        reasons.append(f"In TikTok's Top Ads ({s.tiktok_ads} ad{'s' if s.tiktok_ads > 1 else ''})")

    # ---------- 2. engagement (25)
    er = _tier(s.engagement_rate, [(0.10, 8), (0.06, 6), (0.04, 4), (0.02, 2)]) if s.engagement_rate is not None else None
    sr = _tier(s.share_ratio, [(0.15, 5), (0.08, 3), (0.04, 1)]) if s.share_ratio is not None else None
    ir = None
    if s.intent_ratio is not None:
        ir = _tier(s.intent_ratio, [(0.10, 7), (0.05, 5), (0.02, 3), (0.0001, 1)])
    ctr = _tier(s.best_ctr, [(0.03, 5), (0.02, 3), (0.01, 1)]) if s.best_ctr is not None else None
    engagement, cov_eng = _pillar([(er, 8), (sr, 5), (ir, 7), (ctr, 5)], 25)
    if s.engagement_rate and s.engagement_rate >= 0.04:
        reasons.append(f"{s.engagement_rate * 100:.1f}% engagement on TikTok videos")
    if s.intent_ratio and s.intent_ratio >= 0.02:
        reasons.append(f"{s.intent_ratio * 100:.0f}% of comments ask where to buy / price")
    if s.best_ctr and s.best_ctr >= 0.02:
        reasons.append(f"{s.best_ctr * 100:.1f}% CTR on TikTok ads")

    # ---------- 3. proven demand (20)
    adv = None
    if s.advertisers:
        n = s.advertisers
        adv = 10 if 3 <= n <= 15 else 6 if (n == 2 or 16 <= n <= 30) else 3 if (n == 1 or n <= 50) else 1
    crt = _tier(s.creators, [(10, 5), (5, 4), (3, 2), (1, 1)]) if s.videos else None
    vws = _tier(s.total_views, [(10_000_000, 5), (2_000_000, 4), (500_000, 2), (100_000, 1)]) if s.total_views else None
    demand, cov_dem = _pillar([(adv, 10), (crt, 5), (vws, 5)], 20)
    if 3 <= s.advertisers <= 15:
        reasons.append(f"{s.advertisers} different stores selling it — validated, not saturated")
    if s.creators >= 3:
        reasons.append(f"{s.creators} creators posting it" +
                       (f", {s.total_views:,} views" if s.total_views else ""))

    # ---------- 4. margin (15)
    mult_pts = price_pts = None
    if s.sell_price_usd:
        p = s.sell_price_usd
        price_pts = 5.0 if 20 <= p <= 60 else 3.0 if (15 <= p < 20 or 60 < p <= 90) else 1.0
    if s.sell_price_usd and s.cost_usd:
        mult = s.sell_price_usd / s.cost_usd
        mult_pts = _tier(mult, [(4, 10), (3, 8), (2.5, 5), (2, 2)])
        if s.cost_estimated:
            mult_pts *= 0.8
        reasons.append(f"Sells ${s.sell_price_usd:.2f} vs {'~' if s.cost_estimated else ''}"
                       f"${s.cost_usd:.2f} cost ({mult:.1f}×)")
    margin, cov_mar = _pillar([(mult_pts, 10), (price_pts, 5)], 15)

    # ---------- 5. freshness (10)
    new_pts = _tier(-(s.first_seen_days), [(-14, 4), (-30, 3), (-60, 2), (-10_000, 1)]) if s.first_seen_days is not None else None
    vel = _tier(s.views_per_hour, [(10_000, 3), (2_000, 2), (500, 1)]) if s.views_per_hour is not None else None
    quality = None
    if s.wow is not None or s.problem is not None:
        q = max(float(s.wow or 0), float(s.problem or 0)) * 0.6 + min(float(s.wow or 0), float(s.problem or 0)) * 0.4
        quality = _tier(q, [(8, 3), (6, 2), (4, 1)])
    freshness, cov_fr = _pillar([(new_pts, 4), (vel, 3), (quality, 3)], 10)
    if s.views_per_hour and s.views_per_hour >= 2_000:
        reasons.append(f"Accelerating: {int(s.views_per_hour):,} views/hour on a recent video")

    # ---------- penalties
    def pen(points: int, why: str):
        penalties.append({"points": points, "reason": why})

    if s.advertisers > 50:
        pen(10, f"Saturated — {s.advertisers} stores already selling it")
    elif s.advertisers > 30:
        pen(5, f"Getting crowded — {s.advertisers} stores")
    if s.fragile_heavy:
        pen(5, "Fragile or heavy — shipping risk")
    if s.seasonal:
        pen(3, "Seasonal demand")
    if s.ip_risk == "low":
        pen(3, "Possible brand look-alike")
    if s.max_days_running is not None and s.max_days_running < 4 and not s.videos:
        pen(5, "Ads too new to prove anything")

    pillars = {"scaling": scaling, "engagement": engagement, "demand": demand,
               "margin": margin, "freshness": freshness}
    breakdown = {k: (round(v, 1) if v is not None else None) for k, v in pillars.items()}
    known_max = sum(PILLARS[k] for k, v in pillars.items() if v is not None)
    earned = sum(v for v in pillars.values() if v is not None)
    raw = 100 * earned / max(known_max, KNOWN_FLOOR) if known_max else 0.0
    n_src = len(s.sources)
    if n_src <= 1 and raw > SINGLE_SOURCE_CAP:
        raw = SINGLE_SOURCE_CAP
    raw -= sum(p["points"] for p in penalties)
    total = int(round(max(0, min(100, raw))))

    confidence = ("high" if n_src >= 2 and known_max >= 75
                  else "medium" if n_src >= 2 or known_max >= 75 else "low")
    missing = [k for k, v in pillars.items() if v is None]
    sig = asdict(s)
    sig["known_points"] = known_max
    sig["missing_pillars"] = missing

    return ScoreResult(
        total=total, breakdown=breakdown, penalties=penalties, reasons=reasons[:7],
        confidence=confidence, excluded=excluded, signals=sig,
    )


# ------------------------------------------------------------- selection

def pick_winners(scored: list[tuple[str, ScoreResult]], max_picks: int = MAX_PICKS,
                 min_picks: int = MIN_PICKS) -> list[tuple[str, ScoreResult, str]]:
    """scored = [(product_id, result)]. Returns [(product_id, result, tier)] ranked."""
    eligible = sorted((x for x in scored if not x[1].excluded), key=lambda x: (x[1].total, x[1].confidence == "high"),
                      reverse=True)
    def is_winner(r: ScoreResult) -> bool:
        return r.total >= WINNER_THRESHOLD and r.confidence != "low"

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
