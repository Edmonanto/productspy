"""Unit economics — deterministic, explicit assumptions, no AI arithmetic.

Definitions (per order, one unit; all amounts in USD unless converted):

    fees                      = price x payment_fee_pct + payment_fee_fixed
    returns allowance         = price x returns_pct           (refunds / damaged / chargebacks)
    variable costs            = product cost + shipping + packaging/fulfilment
                                + fees + returns allowance + other variable costs
    gross profit              = price - product cost          (before shipping, fees, ads)
    contribution before ads   = price - variable costs
    contribution margin %     = contribution before ads / price
    break-even CPA            = contribution before ads       (max ad spend per order to break even)
    break-even ROAS           = price / contribution before ads   (revenue-based ROAS)
    contribution after ads    = contribution before ads - CPA
    ROAS at that CPA          = price / CPA

ROAS is revenue / ad spend — it is not profit. Missing inputs make the result
"incomplete" (None) instead of guessing. The defaults below are labelled
assumptions the user can change in the calculator; the frontend mirror is
src/lib/profit.ts and must stay identical.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Optional

# Labelled default assumptions (shown to the user, editable in the calculator).
DEFAULTS = {
    "shipping_usd": 5.0,          # ePacket/agent line to US/EU, small parcel
    "packaging_usd": 0.5,
    "payment_fee_pct": 3.0,       # Stripe/Shopify Payments ~2.9 %
    "payment_fee_fixed_usd": 0.3,
    "returns_pct": 5.0,           # refunds, damaged, chargebacks
    "other_usd": 0.0,
}

ASSUMPTION_LABELS = {
    "shipping_usd": "Shipping to customer, $5 per order (assumption)",
    "packaging_usd": "Packaging and fulfilment, $0.50 (assumption)",
    "payment_fee_pct": "Payment fees 3% + $0.30 (assumption)",
    "returns_pct": "Returns and refunds allowance 5% of price (assumption)",
}


@dataclass
class Inputs:
    price_usd: Optional[float] = None
    product_cost_usd: Optional[float] = None
    shipping_usd: float = DEFAULTS["shipping_usd"]
    packaging_usd: float = DEFAULTS["packaging_usd"]
    payment_fee_pct: float = DEFAULTS["payment_fee_pct"]
    payment_fee_fixed_usd: float = DEFAULTS["payment_fee_fixed_usd"]
    returns_pct: float = DEFAULTS["returns_pct"]
    other_usd: float = DEFAULTS["other_usd"]
    cpa_usd: Optional[float] = None       # ad cost to acquire one order


@dataclass
class Result:
    complete: bool
    missing: list = field(default_factory=list)
    fees_usd: Optional[float] = None
    returns_usd: Optional[float] = None
    variable_costs_usd: Optional[float] = None
    gross_profit_usd: Optional[float] = None
    contribution_before_ads_usd: Optional[float] = None
    contribution_margin_pct: Optional[float] = None
    break_even_cpa_usd: Optional[float] = None
    break_even_roas: Optional[float] = None
    contribution_after_ads_usd: Optional[float] = None
    margin_after_ads_pct: Optional[float] = None
    roas_at_cpa: Optional[float] = None
    markup: Optional[float] = None


def _r(x: Optional[float], n: int = 2) -> Optional[float]:
    return None if x is None else round(x, n)


def compute(i: Inputs) -> Result:
    missing = [k for k, v in (("selling price", i.price_usd), ("product cost", i.product_cost_usd)) if v is None]
    if missing or not i.price_usd or i.price_usd <= 0:
        return Result(complete=False, missing=missing or ["selling price"])
    price, cost = float(i.price_usd), float(i.product_cost_usd)
    fees = price * i.payment_fee_pct / 100 + i.payment_fee_fixed_usd
    returns = price * i.returns_pct / 100
    variable = cost + i.shipping_usd + i.packaging_usd + fees + returns + i.other_usd
    contrib = price - variable
    res = Result(
        complete=True,
        fees_usd=_r(fees), returns_usd=_r(returns), variable_costs_usd=_r(variable),
        gross_profit_usd=_r(price - cost),
        contribution_before_ads_usd=_r(contrib),
        contribution_margin_pct=_r(contrib / price * 100, 1),
        break_even_cpa_usd=_r(max(contrib, 0.0)),
        break_even_roas=_r(price / contrib) if contrib > 0 else None,
        markup=_r(price / cost) if cost > 0 else None,
    )
    if i.cpa_usd is not None:
        after = contrib - i.cpa_usd
        res.contribution_after_ads_usd = _r(after)
        res.margin_after_ads_pct = _r(after / price * 100, 1)
        res.roas_at_cpa = _r(price / i.cpa_usd) if i.cpa_usd > 0 else None
    else:
        res.missing = ["ad cost per order (CPA)"]
    return res


# Scenario multipliers applied to the user's own inputs — what-ifs, not forecasts.
SCENARIOS = {
    "conservative": {"price": 0.9, "cost": 1.15, "shipping": 1.2, "returns_pct": 1.6, "cpa": 1.3},
    "base": {"price": 1.0, "cost": 1.0, "shipping": 1.0, "returns_pct": 1.0, "cpa": 1.0},
    "optimistic": {"price": 1.05, "cost": 0.95, "shipping": 0.9, "returns_pct": 0.8, "cpa": 0.75},
}


def scenarios(i: Inputs) -> dict[str, dict]:
    out = {}
    for name, m in SCENARIOS.items():
        s = replace(
            i,
            price_usd=None if i.price_usd is None else i.price_usd * m["price"],
            product_cost_usd=None if i.product_cost_usd is None else i.product_cost_usd * m["cost"],
            shipping_usd=i.shipping_usd * m["shipping"],
            returns_pct=i.returns_pct * m["returns_pct"],
            cpa_usd=None if i.cpa_usd is None else i.cpa_usd * m["cpa"],
        )
        out[name] = asdict(compute(s))
    return out


def cpa_sensitivity(i: Inputs, cpas: Optional[list[float]] = None) -> list[dict]:
    base = compute(i)
    if not base.complete:
        return []
    be = base.break_even_cpa_usd or 0
    points = cpas or sorted({round(x, 2) for x in (5, 10, 15, 20, 25, 30, be * 0.5, be) if x > 0})
    return [{"cpa_usd": c, "contribution_after_ads_usd": _r(base.contribution_before_ads_usd - c),
             "roas": _r(i.price_usd / c)} for c in points]


def price_sensitivity(i: Inputs, prices: Optional[list[float]] = None) -> list[dict]:
    if i.price_usd is None or i.product_cost_usd is None:
        return []
    p = i.price_usd
    points = prices or [round(p * f, 2) for f in (0.8, 0.9, 1.0, 1.1, 1.2)]
    rows = []
    for price in points:
        r = compute(replace(i, price_usd=price))
        rows.append({"price_usd": price, "contribution_before_ads_usd": r.contribution_before_ads_usd,
                     "contribution_margin_pct": r.contribution_margin_pct,
                     "break_even_roas": r.break_even_roas,
                     "contribution_after_ads_usd": r.contribution_after_ads_usd})
    return rows


def for_product(price_usd: Optional[float], cost_usd: Optional[float]) -> Result:
    """Product-level estimate with the default assumptions (used by scoring and cards)."""
    return compute(Inputs(price_usd=price_usd, product_cost_usd=cost_usd))
