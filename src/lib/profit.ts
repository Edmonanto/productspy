/**
 * Unit economics — mirror of backend/app/winners/economics.py (keep identical).
 *
 *   fees                     = price × payment fee % + fixed fee
 *   returns allowance        = price × returns %
 *   variable costs           = product + shipping + packaging + fees + returns + other
 *   gross profit             = price − product cost
 *   contribution before ads  = price − variable costs
 *   break-even CPA           = contribution before ads   (max ad spend per order)
 *   break-even ROAS          = price ÷ contribution before ads   (revenue-based)
 *   contribution after ads   = contribution before ads − CPA
 *
 * ROAS is revenue ÷ ad spend — not profit. Missing inputs → incomplete, never guessed.
 */
export interface EconInputs {
  price: number | null;
  productCost: number | null;
  shipping: number;
  packaging: number;
  feePct: number;
  feeFixed: number;
  returnsPct: number;
  other: number;
  cpa: number | null;
}

export const DEFAULT_ASSUMPTIONS = {
  shipping: 5, packaging: 0.5, feePct: 3, feeFixed: 0.3, returnsPct: 5, other: 0,
} as const;

export interface EconResult {
  complete: boolean;
  missing: string[];
  fees: number | null;
  returns: number | null;
  variableCosts: number | null;
  grossProfit: number | null;
  contributionBeforeAds: number | null;
  contributionMarginPct: number | null;
  breakEvenCpa: number | null;
  breakEvenRoas: number | null;
  contributionAfterAds: number | null;
  marginAfterAdsPct: number | null;
  roasAtCpa: number | null;
  markup: number | null;
}

const r2 = (x: number) => Math.round(x * 100) / 100;
const r1 = (x: number) => Math.round(x * 10) / 10;

export function computeEconomics(i: EconInputs): EconResult {
  const empty: EconResult = {
    complete: false, missing: [], fees: null, returns: null, variableCosts: null, grossProfit: null,
    contributionBeforeAds: null, contributionMarginPct: null, breakEvenCpa: null, breakEvenRoas: null,
    contributionAfterAds: null, marginAfterAdsPct: null, roasAtCpa: null, markup: null,
  };
  const missing: string[] = [];
  if (i.price == null || i.price <= 0) missing.push("selling price");
  if (i.productCost == null) missing.push("product cost");
  if (missing.length) return { ...empty, missing };
  const price = i.price!, cost = i.productCost!;
  const fees = price * i.feePct / 100 + i.feeFixed;
  const returns = price * i.returnsPct / 100;
  const variable = cost + i.shipping + i.packaging + fees + returns + i.other;
  const contrib = price - variable;
  const res: EconResult = {
    ...empty,
    complete: true,
    fees: r2(fees), returns: r2(returns), variableCosts: r2(variable),
    grossProfit: r2(price - cost),
    contributionBeforeAds: r2(contrib),
    contributionMarginPct: r1(contrib / price * 100),
    breakEvenCpa: r2(Math.max(contrib, 0)),
    breakEvenRoas: contrib > 0 ? r2(price / contrib) : null,
    markup: cost > 0 ? r2(price / cost) : null,
  };
  if (i.cpa != null) {
    const after = contrib - i.cpa;
    res.contributionAfterAds = r2(after);
    res.marginAfterAdsPct = r1(after / price * 100);
    res.roasAtCpa = i.cpa > 0 ? r2(price / i.cpa) : null;
  } else {
    res.missing = ["ad cost per order (CPA)"];
  }
  return res;
}

/** What-ifs applied to the user's own inputs — not sales forecasts. */
export const SCENARIOS = {
  conservative: { price: 0.9, cost: 1.15, shipping: 1.2, returnsPct: 1.6, cpa: 1.3 },
  base: { price: 1, cost: 1, shipping: 1, returnsPct: 1, cpa: 1 },
  optimistic: { price: 1.05, cost: 0.95, shipping: 0.9, returnsPct: 0.8, cpa: 0.75 },
} as const;

export function scenarioResults(i: EconInputs) {
  return (Object.keys(SCENARIOS) as (keyof typeof SCENARIOS)[]).map((name) => {
    const m = SCENARIOS[name];
    return {
      name,
      result: computeEconomics({
        ...i,
        price: i.price == null ? null : i.price * m.price,
        productCost: i.productCost == null ? null : i.productCost * m.cost,
        shipping: i.shipping * m.shipping,
        returnsPct: i.returnsPct * m.returnsPct,
        cpa: i.cpa == null ? null : i.cpa * m.cpa,
      }),
    };
  });
}

export function cpaSensitivity(i: EconInputs, points?: number[]) {
  const base = computeEconomics(i);
  if (!base.complete) return [];
  const be = base.breakEvenCpa ?? 0;
  const pts = points ?? Array.from(new Set([5, 10, 15, 20, 25, 30, r2(be * 0.5), r2(be)]))
    .filter((x) => x > 0).sort((a, b) => a - b);
  return pts.map((c) => ({ cpa: c, contributionAfterAds: r2(base.contributionBeforeAds! - c), roas: r2(i.price! / c) }));
}

export function priceSensitivity(i: EconInputs) {
  if (i.price == null || i.productCost == null) return [];
  return [0.8, 0.9, 1, 1.1, 1.2].map((f) => {
    const price = r2(i.price! * f);
    const r = computeEconomics({ ...i, price });
    return { price, contributionBeforeAds: r.contributionBeforeAds, marginPct: r.contributionMarginPct,
             breakEvenRoas: r.breakEvenRoas, contributionAfterAds: r.contributionAfterAds };
  });
}

/** A starting sell price: landed cost × 3, rounded to a .99 ending. */
export function suggestedSellPrice(landedCost: number): number {
  const raw = landedCost * 3;
  return raw < 1 ? Math.round(raw * 100) / 100 : Math.max(0.99, Math.ceil(raw) - 0.01);
}
