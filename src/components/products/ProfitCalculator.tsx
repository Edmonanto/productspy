"use client";

import { useEffect, useMemo, useState } from "react";
import { Calculator, Info } from "lucide-react";
import type { Product } from "@/lib/api";
import { computeProfit, suggestedSellPrice, tierFor } from "@/lib/profit";

interface Props {
  product: Product;
  /** Opens the quote form, pre-filled with the quantity entered here. */
  onRequestQuote: (quantity: number) => void;
}

const usd = (n: number) =>
  n.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 });

function Field({
  label, value, onChange, prefix, suffix, step = "0.01", hint,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  prefix?: string;
  suffix?: string;
  step?: string;
  hint?: string;
}) {
  return (
    <label className="block">
      <span className="text-zinc-500 text-xs">{label}</span>
      <div className="mt-1 flex items-center bg-zinc-800 border border-zinc-700 rounded-lg focus-within:border-violet-500">
        {prefix && <span className="pl-2.5 text-zinc-500 text-sm">{prefix}</span>}
        <input
          type="number"
          inputMode="decimal"
          min={0}
          step={step}
          value={Number.isFinite(value) ? value : 0}
          onChange={(e) => onChange(Math.max(0, parseFloat(e.target.value) || 0))}
          className="w-full bg-transparent px-2.5 py-2 text-white text-sm outline-none"
        />
        {suffix && <span className="pr-2.5 text-zinc-500 text-sm">{suffix}</span>}
      </div>
      {hint && <span className="text-zinc-600 text-[11px] mt-1 block">{hint}</span>}
    </label>
  );
}

export default function ProfitCalculator({ product, onRequestQuote }: Props) {
  const details = product.details;
  const tiers = useMemo(() => details?.price_tiers ?? [], [details]);
  const moq = details?.moq ?? 1;

  const [qty, setQty] = useState(Math.max(moq, 1));
  const tier = tierFor(tiers, qty);
  const tierCost = tier?.price_usd ?? product.cost_usd ?? 0;

  // Unit cost follows the tier for the chosen quantity until the user types
  // their own (e.g. a price they negotiated or were quoted).
  const [costOverride, setCostOverride] = useState<number | null>(null);
  const unitCost = costOverride ?? tierCost;

  const [shipping, setShipping] = useState(details?.shipping_estimate_usd ?? 5);
  const [sellPrice, setSellPrice] = useState(() =>
    suggestedSellPrice(tierCost + (details?.shipping_estimate_usd ?? 5))
  );
  const [feePct, setFeePct] = useState(5);
  const [adCost, setAdCost] = useState(0);
  const [units, setUnits] = useState(100);

  // Details arrive after the first render on a cold product page.
  useEffect(() => {
    if (details?.shipping_estimate_usd != null) setShipping(details.shipping_estimate_usd);
    if (details?.moq) setQty((q) => Math.max(q, details.moq ?? 1));
  }, [details]);

  const r = computeProfit({
    unitCostUsd: unitCost,
    shippingUsd: shipping,
    sellPriceUsd: sellPrice,
    feePct,
    adCostPerSaleUsd: adCost,
    unitsPerMonth: units,
  });
  const losing = r.profitPerUnit < 0;
  const rate = details?.cny_per_usd;

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-5">
      <div className="flex items-center gap-2">
        <Calculator size={16} className="text-violet-400" />
        <h2 className="text-white font-semibold">Profit calculator</h2>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <Field
          label="Order quantity"
          value={qty}
          step="1"
          onChange={(v) => setQty(Math.max(1, Math.round(v)))}
          hint={details?.moq ? `Minimum order: ${details.moq}${details.unit ? ` ${details.unit}` : ""}` : undefined}
        />
        <Field
          label="Supplier cost / unit"
          prefix="$"
          value={Number(unitCost.toFixed(2))}
          onChange={(v) => setCostOverride(v)}
          hint={
            costOverride != null
              ? "Your price"
              : tier && rate
                ? `¥${tier.price_cny} at ${tier.min_qty}+ (¥${rate}/$)`
                : "From 1688"
          }
        />
        <Field
          label="Shipping to customer / unit"
          prefix="$"
          value={shipping}
          onChange={setShipping}
          hint={
            details?.weight_kg
              ? `Estimate for ${details.weight_kg} kg — check with your agent`
              : "Your estimate"
          }
        />
        <Field label="Your selling price" prefix="$" value={sellPrice} onChange={setSellPrice} />
        <Field
          label="Payment + platform fees"
          suffix="%"
          step="0.1"
          value={feePct}
          onChange={setFeePct}
          hint="Stripe/PayPal ≈ 3%, plus your store's fee"
        />
        <Field label="Ad cost per sale" prefix="$" value={adCost} onChange={setAdCost} hint="Average ad spend to win one order" />
        <Field label="Sales per month" step="1" value={units} onChange={(v) => setUnits(Math.round(v))} />
      </div>

      {/* Results */}
      <div className="grid grid-cols-2 gap-3">
        {[
          { label: "Landed cost / unit", value: usd(r.landedCost), tone: "text-white" },
          { label: "Fees / unit", value: usd(r.fees), tone: "text-white" },
          {
            label: "Profit / unit",
            value: usd(r.profitPerUnit),
            tone: losing ? "text-red-400" : "text-emerald-400",
          },
          {
            label: "Margin",
            value: r.marginPct == null ? "—" : `${r.marginPct.toFixed(0)}%`,
            tone: losing ? "text-red-400" : "text-emerald-400",
          },
        ].map(({ label, value, tone }) => (
          <div key={label} className="bg-zinc-800/60 rounded-lg p-3">
            <div className="text-zinc-500 text-xs">{label}</div>
            <div className={`font-bold text-sm mt-0.5 ${tone}`}>{value}</div>
          </div>
        ))}
      </div>

      <div className={`rounded-lg p-4 border ${losing ? "bg-red-500/10 border-red-500/30" : "bg-emerald-500/10 border-emerald-500/30"}`}>
        <div className="text-zinc-400 text-xs">Estimated monthly profit at {units.toLocaleString()} sales</div>
        <div className={`text-2xl font-bold mt-1 ${losing ? "text-red-400" : "text-emerald-400"}`}>
          {usd(r.monthlyProfit)}
        </div>
        <div className="text-zinc-500 text-xs mt-1">
          on {usd(r.monthlyRevenue)} revenue ·{" "}
          {r.breakEvenRoas == null
            ? "no room for ad spend at this price"
            : `break-even ROAS ${r.breakEvenRoas.toFixed(2)}×`}
        </div>
        {qty > 1 && (
          <div className="text-zinc-500 text-xs mt-1">
            Stock order of {qty.toLocaleString()} costs {usd(qty * unitCost)} before shipping
          </div>
        )}
      </div>

      <div className="flex items-start gap-2 text-zinc-500 text-[11px] leading-relaxed">
        <Info size={12} className="mt-0.5 shrink-0" />
        <span>
          Estimates. Supplier prices come from 1688{details?.fetched_at ? "" : " search results"} and
          shipping is a guess until you confirm it. For an exact price at your quantity and
          destination, request a quote.
        </span>
      </div>

      <button
        onClick={() => onRequestQuote(qty)}
        className="w-full bg-violet-600 hover:bg-violet-500 text-white text-sm font-semibold py-2.5 rounded-lg transition-colors"
      >
        Request a quote for {qty.toLocaleString()} units
      </button>
    </div>
  );
}
