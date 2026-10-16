/**
 * Dropshipping unit economics. Pure functions so the calculator UI and any
 * future server-side use agree on the maths.
 *
 *   landed cost  = supplier unit cost + shipping per unit
 *   fees         = sell price x fee %          (payment processor + platform)
 *   profit/unit  = sell price - landed cost - fees - ad cost per sale
 *   break-even ROAS = sell price / (sell price - landed - fees)
 *       — the ad return you need just to not lose money; above it you profit
 */
import type { PriceTier } from "./api";

export interface ProfitInputs {
  unitCostUsd: number;
  shippingUsd: number;
  sellPriceUsd: number;
  feePct: number;        // e.g. 5 for 5%
  adCostPerSaleUsd: number;
  unitsPerMonth: number;
}

export interface ProfitResult {
  landedCost: number;
  fees: number;
  profitPerUnit: number;
  marginPct: number | null;   // of sell price
  monthlyRevenue: number;
  monthlyProfit: number;
  breakEvenRoas: number | null; // null when there is no room for ads at all
}

export function computeProfit(i: ProfitInputs): ProfitResult {
  const landedCost = i.unitCostUsd + i.shippingUsd;
  const fees = i.sellPriceUsd * (i.feePct / 100);
  const contribution = i.sellPriceUsd - landedCost - fees; // before ads
  const profitPerUnit = contribution - i.adCostPerSaleUsd;
  return {
    landedCost,
    fees,
    profitPerUnit,
    marginPct: i.sellPriceUsd > 0 ? (profitPerUnit / i.sellPriceUsd) * 100 : null,
    monthlyRevenue: i.sellPriceUsd * i.unitsPerMonth,
    monthlyProfit: profitPerUnit * i.unitsPerMonth,
    breakEvenRoas: contribution > 0 ? i.sellPriceUsd / contribution : null,
  };
}

/** The tier that applies when ordering `qty` units: the highest min_qty <= qty. */
export function tierFor(tiers: PriceTier[], qty: number): PriceTier | null {
  const sorted = [...tiers].sort((a, b) => a.min_qty - b.min_qty);
  let match: PriceTier | null = null;
  for (const t of sorted) if (qty >= t.min_qty) match = t;
  return match ?? sorted[0] ?? null;
}

/** A starting sell price: landed cost x 3, rounded to a .99 ending. */
export function suggestedSellPrice(landedCost: number): number {
  const raw = landedCost * 3;
  return raw < 1 ? Math.round(raw * 100) / 100 : Math.max(0.99, Math.ceil(raw) - 0.01);
}
