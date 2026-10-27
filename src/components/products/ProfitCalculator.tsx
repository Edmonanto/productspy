"use client";

import { useMemo, useState } from "react";
import { Calculator, Info } from "lucide-react";
import {
  computeEconomics, cpaSensitivity, DEFAULT_ASSUMPTIONS, EconInputs, priceSensitivity,
  scenarioResults, suggestedSellPrice,
} from "@/lib/profit";
import { cn } from "@/lib/utils";

interface Props {
  /** What competitors sell it for (from their store page), if known. USD. */
  priceUsd: number | null;
  /** Supplier unit cost: a supplier listing, or an AI estimate. USD. */
  costUsd: number | null;
  costEstimated: boolean;
  /** Opens the quote form, pre-filled with the quantity entered here. */
  onRequestQuote: (quantity: number) => void;
  /** Section number in the product report. */
  n?: number;
}

const CURRENCIES = ["USD", "EUR", "GBP", "CAD", "AUD", "AED", "SAR"];

function Field({
  label, value, onChange, prefix, suffix, step = "0.01", hint, tag,
}: {
  label: string; value: number | null; onChange: (v: number | null) => void;
  prefix?: string; suffix?: string; step?: string; hint?: string; tag?: string;
}) {
  return (
    <label className="block">
      <span className="flex items-center gap-1.5 text-zinc-400 text-xs">
        {label}
        {tag && <span className="text-[10px] text-zinc-500 bg-zinc-800 rounded px-1">{tag}</span>}
      </span>
      <div className="mt-1 flex items-center bg-zinc-800 border border-zinc-700 rounded-lg focus-within:border-violet-500">
        {prefix && <span className="pl-2.5 text-zinc-500 text-sm">{prefix}</span>}
        <input
          type="number"
          inputMode="decimal"
          min={0}
          step={step}
          value={value == null || !Number.isFinite(value) ? "" : value}
          placeholder="—"
          onChange={(e) => onChange(e.target.value === "" ? null : Math.max(0, parseFloat(e.target.value) || 0))}
          className="w-full bg-transparent px-2.5 py-2 text-white text-sm outline-none placeholder:text-zinc-600"
        />
        {suffix && <span className="pr-2.5 text-zinc-500 text-sm">{suffix}</span>}
      </div>
      {hint && <span className="text-zinc-500 text-[11px] mt-1 block">{hint}</span>}
    </label>
  );
}

function Metric({ label, value, tone = "text-white", sub }: { label: string; value: string; tone?: string; sub?: string }) {
  return (
    <div className="bg-zinc-800/60 rounded-lg p-3 min-w-0">
      <div className="text-zinc-500 text-[11px] leading-tight">{label}</div>
      <div className={cn("font-semibold text-sm mt-1 tabular-nums", tone)}>{value}</div>
      {sub && <div className="text-zinc-500 text-[10px] mt-0.5">{sub}</div>}
    </div>
  );
}

export default function ProfitCalculator({ priceUsd, costUsd, costEstimated, onRequestQuote, n }: Props) {
  const [currency, setCurrency] = useState("USD");
  const [rate, setRate] = useState<number | null>(1);              // 1 USD = rate × currency (user-entered)
  const [qty, setQty] = useState<number | null>(100);
  const conv = currency === "USD" ? 1 : rate ?? 1;
  const toLocal = (usd: number | null) => (usd == null ? null : Math.round(usd * conv * 100) / 100);

  const [i, setI] = useState<EconInputs>(() => ({
    price: priceUsd ?? (costUsd != null ? suggestedSellPrice(costUsd + DEFAULT_ASSUMPTIONS.shipping) : null),
    productCost: costUsd,
    shipping: DEFAULT_ASSUMPTIONS.shipping,
    packaging: DEFAULT_ASSUMPTIONS.packaging,
    feePct: DEFAULT_ASSUMPTIONS.feePct,
    feeFixed: DEFAULT_ASSUMPTIONS.feeFixed,
    returnsPct: DEFAULT_ASSUMPTIONS.returnsPct,
    other: DEFAULT_ASSUMPTIONS.other,
    cpa: null,
  }));
  const set = (k: keyof EconInputs) => (v: number | null) => setI((cur) => ({ ...cur, [k]: v ?? (k === "price" || k === "productCost" || k === "cpa" ? null : 0) }));

  // Inputs are entered in the chosen currency; the maths is currency-neutral.
  const r = useMemo(() => computeEconomics(i), [i]);
  const scen = useMemo(() => scenarioResults(i), [i]);
  const cpaRows = useMemo(() => cpaSensitivity(i), [i]);
  const priceRows = useMemo(() => priceSensitivity(i), [i]);

  const sym = currency === "USD" ? "$" : currency === "EUR" ? "€" : currency === "GBP" ? "£" : `${currency} `;
  const money = (n: number | null | undefined) =>
    n == null ? "—" : `${n < 0 ? "−" : ""}${sym}${Math.abs(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  const tone = (n: number | null | undefined) => (n == null ? "text-zinc-400" : n < 0 ? "text-red-400" : "text-emerald-400");

  const switchCurrency = (c: string) => {
    // Re-express the observed USD values in the new currency; user edits stay as typed.
    const nextRate = c === "USD" ? 1 : rate ?? 1;
    setCurrency(c);
    if (c === "USD") setRate(1);
    setI((cur) => ({
      ...cur,
      price: priceUsd != null ? Math.round(priceUsd * nextRate * 100) / 100 : cur.price,
      productCost: costUsd != null ? Math.round(costUsd * nextRate * 100) / 100 : cur.productCost,
    }));
  };

  return (
    <section id="profit" className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 md:p-5 space-y-5 scroll-mt-28" aria-labelledby="calc-h">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          {n != null ? <span className="text-zinc-500 text-xs tabular-nums">{String(n).padStart(2, "0")}</span>
            : <Calculator size={16} className="text-violet-400" />}
          <h3 id="calc-h" className="text-white font-semibold">Pricing & profitability calculator</h3>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <label className="flex items-center gap-1.5 text-zinc-400">
            Currency
            <select value={currency} onChange={(e) => switchCurrency(e.target.value)}
                    className="bg-zinc-800 border border-zinc-700 rounded-md px-2 py-1.5 text-zinc-200">
              {CURRENCIES.map((c) => <option key={c}>{c}</option>)}
            </select>
          </label>
          {currency !== "USD" && (
            <label className="flex items-center gap-1.5 text-zinc-400">
              1 USD =
              <input type="number" step="0.0001" min={0} value={rate ?? ""} aria-label="Exchange rate"
                     onChange={(e) => setRate(e.target.value === "" ? null : parseFloat(e.target.value))}
                     className="w-20 bg-zinc-800 border border-zinc-700 rounded-md px-2 py-1.5 text-zinc-200" />
              {currency}
            </label>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Field label="Selling price" prefix={sym} value={i.price} onChange={set("price")} tag="input"
               hint={priceUsd != null ? `Competitor price: ${money(toLocal(priceUsd))}` : "No competitor price found"} />
        <Field label="Product cost / unit" prefix={sym} value={i.productCost} onChange={set("productCost")} tag="input"
               hint={costUsd == null ? "Not found — enter your quote" : costEstimated ? "AI estimate — confirm with a quote" : "From a supplier listing"} />
        <Field label="Shipping / order" prefix={sym} value={i.shipping} onChange={set("shipping")} tag="assumption"
               hint="Check with your agent" />
        <Field label="Packaging" prefix={sym} value={i.packaging} onChange={set("packaging")} tag="assumption" />
        <Field label="Payment fees" suffix="%" step="0.1" value={i.feePct} onChange={set("feePct")} tag="assumption"
               hint="Stripe / Shopify Payments ≈ 2.9%" />
        <Field label="Fixed fee / order" prefix={sym} value={i.feeFixed} onChange={set("feeFixed")} tag="assumption" />
        <Field label="Returns (% of price)" suffix="%" step="0.5" value={i.returnsPct} onChange={set("returnsPct")} tag="assumption" />
        <Field label="Other variable costs" prefix={sym} value={i.other} onChange={set("other")} />
        <Field label="Ad cost / order (CPA)" prefix={sym} value={i.cpa} onChange={set("cpa")} tag="input"
               hint="Average ad spend to win one order" />
      </div>

      {!r.complete ? (
        <div className="text-sm text-amber-200 bg-amber-500/10 border border-amber-500/20 rounded-lg px-3 py-2">
          Incomplete — enter the {r.missing.join(" and ")} to calculate. Nothing is estimated for you here.
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            <Metric label="Gross profit (price − product cost)" value={money(r.grossProfit)} />
            <Metric label="Variable costs / order" value={money(r.variableCosts)}
                    sub={`fees ${money(r.fees)} · returns ${money(r.returns)}`} />
            <Metric label="Contribution before ads" value={money(r.contributionBeforeAds)} tone={tone(r.contributionBeforeAds)}
                    sub={r.contributionMarginPct != null ? `${r.contributionMarginPct}% of price` : undefined} />
            <Metric label="Contribution after ads" value={r.contributionAfterAds == null ? "Enter CPA" : money(r.contributionAfterAds)}
                    tone={tone(r.contributionAfterAds)}
                    sub={r.marginAfterAdsPct != null ? `${r.marginAfterAdsPct}% of price` : undefined} />
            <Metric label="Break-even CPA (max ad cost / order)" value={money(r.breakEvenCpa)} />
            <Metric label="Break-even ROAS (revenue ÷ ad spend)" value={r.breakEvenRoas ? `${r.breakEvenRoas.toFixed(2)}×` : "No room for ads"}
                    tone={r.breakEvenRoas ? "text-white" : "text-red-400"} />
            <Metric label="ROAS at your CPA" value={r.roasAtCpa ? `${r.roasAtCpa.toFixed(2)}×` : "—"} />
            <Metric label="Markup on product cost" value={r.markup ? `${r.markup.toFixed(1)}×` : "—"} />
          </div>

          <div className="grid lg:grid-cols-3 gap-4">
            <div className="space-y-2">
              <h4 className="text-zinc-300 text-xs font-semibold">Scenarios (what-ifs, not forecasts)</h4>
              <table className="w-full text-xs">
                <thead><tr className="text-zinc-500 text-left"><th className="font-normal py-1">Case</th><th className="font-normal">Before ads</th><th className="font-normal">After ads</th></tr></thead>
                <tbody>
                  {scen.map(({ name, result }) => (
                    <tr key={name} className="border-t border-zinc-800">
                      <td className="py-1.5 capitalize text-zinc-300">{name}</td>
                      <td className={cn("tabular-nums", tone(result.contributionBeforeAds))}>{money(result.contributionBeforeAds)}</td>
                      <td className={cn("tabular-nums", tone(result.contributionAfterAds))}>{result.contributionAfterAds == null ? "—" : money(result.contributionAfterAds)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="text-zinc-500 text-[11px]">Conservative: price −10%, cost +15%, shipping +20%, returns ×1.6, CPA +30%. Optimistic: price +5%, cost −5%, CPA −25%.</p>
            </div>
            <div className="space-y-2">
              <h4 className="text-zinc-300 text-xs font-semibold">Profit per order at different ad costs</h4>
              <table className="w-full text-xs">
                <thead><tr className="text-zinc-500 text-left"><th className="font-normal py-1">CPA</th><th className="font-normal">ROAS</th><th className="font-normal">After ads</th></tr></thead>
                <tbody>
                  {cpaRows.map((row) => (
                    <tr key={row.cpa} className="border-t border-zinc-800">
                      <td className="py-1.5 tabular-nums text-zinc-300">{money(row.cpa)}</td>
                      <td className="tabular-nums text-zinc-400">{row.roas.toFixed(2)}×</td>
                      <td className={cn("tabular-nums", tone(row.contributionAfterAds))}>{money(row.contributionAfterAds)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="space-y-2">
              <h4 className="text-zinc-300 text-xs font-semibold">Outcomes at different selling prices</h4>
              <table className="w-full text-xs">
                <thead><tr className="text-zinc-500 text-left"><th className="font-normal py-1">Price</th><th className="font-normal">Margin</th><th className="font-normal">BE ROAS</th></tr></thead>
                <tbody>
                  {priceRows.map((row) => (
                    <tr key={row.price} className={cn("border-t border-zinc-800", row.price === i.price && "bg-zinc-800/40")}>
                      <td className="py-1.5 tabular-nums text-zinc-300">{money(row.price)}</td>
                      <td className={cn("tabular-nums", tone(row.contributionBeforeAds))}>{row.marginPct == null ? "—" : `${row.marginPct}%`}</td>
                      <td className="tabular-nums text-zinc-400">{row.breakEvenRoas ? `${row.breakEvenRoas.toFixed(2)}×` : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      <div className="flex items-start gap-2 text-zinc-500 text-[11px] leading-relaxed">
        <Info size={12} className="mt-0.5 shrink-0" />
        <span>
          Inputs tagged “assumption” are starting values — replace them with your own. Results are calculated from your
          inputs and are not sales forecasts. ROAS is revenue ÷ ad spend, not profit.
          {currency !== "USD" && " Observed prices are converted with the rate you entered."}
        </span>
      </div>

      <div className="flex flex-col sm:flex-row gap-2 sm:items-end print:hidden">
        <div className="w-full sm:w-40">
          <Field label="Order quantity" step="1" value={qty} onChange={(v) => setQty(v == null ? null : Math.max(1, Math.round(v)))} />
        </div>
        <button
          onClick={() => onRequestQuote(qty ?? 100)}
          className="flex-1 bg-violet-600 hover:bg-violet-500 text-white text-sm font-semibold py-2.5 rounded-lg transition-colors"
        >
          Request a supplier quote for {(qty ?? 100).toLocaleString()} units
        </button>
      </div>
    </section>
  );
}
