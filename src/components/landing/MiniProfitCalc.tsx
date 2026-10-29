"use client";

import { useState } from "react";
import { computeEconomics, DEFAULT_ASSUMPTIONS } from "@/lib/profit";
import { cn } from "@/lib/utils";

const usd = (n: number | null | undefined) => (n == null ? "—" : `$${n.toFixed(2)}`);

function Slider({ label, value, min, max, step, onChange }: {
  label: string; value: number; min: number; max: number; step: number; onChange: (v: number) => void;
}) {
  return (
    <label className="block">
      <div className="flex justify-between text-xs mb-1.5">
        <span className="text-zinc-400">{label}</span>
        <span className="text-white font-semibold tabular-nums">${value.toFixed(2)}</span>
      </div>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))}
             className="w-full accent-violet-500" aria-label={label} />
    </label>
  );
}

/** Free, no-login profit check — same maths as the in-app calculator. */
export default function MiniProfitCalc() {
  const [price, setPrice] = useState(34.99);
  const [cost, setCost] = useState(8);
  const [cpa, setCpa] = useState(12);
  const r = computeEconomics({ ...DEFAULT_ASSUMPTIONS, price, productCost: cost, cpa });
  const profit = r.contributionAfterAds ?? 0;
  const good = profit > 0;

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5 sm:p-6 grid md:grid-cols-2 gap-6">
      <div className="space-y-5">
        <Slider label="You sell it for" value={price} min={5} max={120} step={0.5} onChange={setPrice} />
        <Slider label="Supplier cost" value={cost} min={1} max={60} step={0.5} onChange={setCost} />
        <Slider label="Ad cost per sale" value={cpa} min={0} max={60} step={0.5} onChange={setCpa} />
        <p className="text-[11px] text-zinc-500">Includes ${DEFAULT_ASSUMPTIONS.shipping} shipping, ${DEFAULT_ASSUMPTIONS.packaging.toFixed(2)} packaging, {DEFAULT_ASSUMPTIONS.feePct}% + ${DEFAULT_ASSUMPTIONS.feeFixed.toFixed(2)} payment fees and {DEFAULT_ASSUMPTIONS.returnsPct}% returns.</p>
      </div>
      <div className="flex flex-col justify-center gap-3">
        <div className={cn("rounded-xl p-5 text-center border", good ? "bg-emerald-500/10 border-emerald-500/30" : "bg-red-500/10 border-red-500/30")}>
          <div className="text-xs text-zinc-400">Profit per order</div>
          <div className={cn("text-4xl font-extrabold tabular-nums", good ? "text-emerald-300" : "text-red-300")}>{usd(r.contributionAfterAds)}</div>
          <div className="text-xs text-zinc-400 mt-1">{good ? "This product can work." : "You lose money on every sale."}</div>
        </div>
        <div className="grid grid-cols-2 gap-3 text-center">
          <div className="bg-zinc-800/60 rounded-xl p-3">
            <div className="text-[11px] text-zinc-400">Max ad cost per sale</div>
            <div className="text-lg font-bold text-white tabular-nums">{usd(r.breakEvenCpa)}</div>
          </div>
          <div className="bg-zinc-800/60 rounded-xl p-3">
            <div className="text-[11px] text-zinc-400">Break-even ROAS</div>
            <div className="text-lg font-bold text-white tabular-nums">{r.breakEvenRoas != null ? `${r.breakEvenRoas}×` : "—"}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
