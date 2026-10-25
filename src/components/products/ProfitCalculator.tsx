"use client";

import { useState } from "react";
import { Calculator, Info } from "lucide-react";
import { computeProfit, suggestedSellPrice } from "@/lib/profit";

interface Props {
  /** What competitors sell it for (from their store page), if known. */
  priceUsd: number | null;
  /** Supplier unit cost: an AliExpress listing, or Claude's estimate. */
  costUsd: number | null;
  costEstimated: boolean;
  /** Opens the quote form, pre-filled with the quantity entered here. */
  onRequestQuote: (quantity: number) => void;
}

const DEFAULT_SHIPPING = 5;

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

export default function ProfitCalculator({ priceUsd, costUsd, costEstimated, onRequestQuote }: Props) {
  const [qty, setQty] = useState(100);
  const [unitCost, setUnitCost] = useState(costUsd ?? 0);
  const [shipping, setShipping] = useState(DEFAULT_SHIPPING);
  // Start from what competitors charge; without that, a 3x landed-cost guess.
  const [sellPrice, setSellPrice] = useState(
    () => priceUsd ?? suggestedSellPrice((costUsd ?? 0) + DEFAULT_SHIPPING)
  );
  const [feePct, setFeePct] = useState(5);
  const [adCost, setAdCost] = useState(0);
  const [units, setUnits] = useState(100);

  const r = computeProfit({
    unitCostUsd: unitCost,
    shippingUsd: shipping,
    sellPriceUsd: sellPrice,
    feePct,
    adCostPerSaleUsd: adCost,
    unitsPerMonth: units,
  });
  const losing = r.profitPerUnit < 0;

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
          hint="For a quote or a stock order"
        />
        <Field
          label="Supplier cost / unit"
          prefix="$"
          value={Number(unitCost.toFixed(2))}
          onChange={setUnitCost}
          hint={costUsd == null ? "Not found yet — enter yours" : costEstimated ? "AI estimate — confirm with a quote" : "From a supplier listing"}
        />
        <Field
          label="Shipping to customer / unit"
          prefix="$"
          value={shipping}
          onChange={setShipping}
          hint="Your estimate — check with your agent"
        />
        <Field
          label="Your selling price"
          prefix="$"
          value={sellPrice}
          onChange={setSellPrice}
          hint={priceUsd != null ? "What competitors charge" : undefined}
        />
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
          Estimates. The cost is a supplier listing or an AI estimate, and shipping is a guess
          until you confirm it. For an exact price at your quantity and
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
