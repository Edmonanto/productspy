"use client";

import { Suspense } from "react";
import Link from "next/link";
import useSWR from "swr";
import { Columns3, ImageOff, Lock, X } from "lucide-react";
import Topbar from "@/components/layout/Topbar";
import ScoreRing from "@/components/winners/ScoreRing";
import ProductImage from "@/components/products/ProductImage";
import { TrendBadge } from "@/components/research/TrendPanel";
import { CompareItem, researchApi } from "@/lib/api";
import { useCompare } from "@/lib/compare";
import { useMarket } from "@/lib/useMarket";
import { cn, formatPrice } from "@/lib/utils";

type Row = { label: string; render: (i: CompareItem) => React.ReactNode; best?: (items: CompareItem[]) => string | null };

const bestBy = (get: (i: CompareItem) => number | null | undefined, high = true) => (items: CompareItem[]) => {
  const vals = items.map((i) => ({ id: i.id, v: get(i) })).filter((x) => x.v != null) as { id: string; v: number }[];
  if (vals.length < 2) return null;
  return vals.reduce((a, b) => ((high ? b.v > a.v : b.v < a.v) ? b : a)).id;
};

function CompareInner() {
  const { market } = useMarket();
  const { ids, toggle } = useCompare();
  const { data, error, isLoading } = useSWR(market && ids.length ? ["compare", ids.join(","), market] : null,
    () => researchApi.compare(ids, market!));
  const err = error as (Error & { code?: string }) | undefined;

  const criteriaRows: Row[] = (data?.criteria ?? []).map((c) => ({
    label: `${c.label} (${Math.round(c.max)})`,
    render: (i) => {
      const v = i.breakdown?.[c.key];
      return v == null ? <span className="text-zinc-500">no data</span> : <span className="tabular-nums">{Math.round(v)}</span>;
    },
    best: bestBy((i) => i.breakdown?.[c.key] ?? null),
  }));

  const rows: Row[] = [
    { label: "Opportunity score", render: (i) => (i.score == null ? "—" : <span className="font-semibold tabular-nums">{i.score}</span>), best: bestBy((i) => i.score) },
    { label: "Evidence confidence", render: (i) => <span className="capitalize">{i.confidence ?? "—"}</span> },
    { label: "Trend", render: (i) => <TrendBadge trend={i.trend} /> },
    { label: "Competitor price", render: (i) => formatPrice(i.price_usd) },
    { label: "Product cost", render: (i) => <>{formatPrice(i.cost_usd)}{i.cost_estimated && <span className="text-zinc-500 text-[11px]"> (AI est.)</span>}</>, best: bestBy((i) => i.cost_usd, false) },
    { label: "Contribution before ads", render: (i) => (i.economics.complete ? `$${i.economics.contribution_before_ads_usd?.toFixed(2)}` : <span className="text-zinc-500">incomplete</span>), best: bestBy((i) => i.economics.contribution_before_ads_usd) },
    { label: "Margin before ads", render: (i) => (i.economics.contribution_margin_pct == null ? "—" : `${i.economics.contribution_margin_pct}%`), best: bestBy((i) => i.economics.contribution_margin_pct) },
    { label: "Break-even ROAS", render: (i) => (i.economics.break_even_roas ? `${i.economics.break_even_roas.toFixed(2)}×` : "—"), best: bestBy((i) => i.economics.break_even_roas, false) },
    { label: "Stores advertising", render: (i) => i.stores ?? "—" },
    { label: "TikTok videos", render: (i) => i.videos ?? "—" },
    ...criteriaRows,
    { label: "Main weakness", render: (i) => <span className="text-xs text-zinc-400">{i.excluded ? `Excluded: ${i.excluded}` : i.weaknesses[0] ?? "—"}</span> },
  ];

  return (
    <div className="p-4 md:p-6 max-w-6xl mx-auto w-full space-y-4">
      <div>
        <h2 className="text-white text-xl font-semibold flex items-center gap-2"><Columns3 size={18} className="text-violet-300" /> Compare products</h2>
        <p className="text-zinc-400 text-sm mt-1">Side by side on the same evidence and assumptions. The best value in each row is highlighted.</p>
      </div>

      {ids.length === 0 ? (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-10 text-center space-y-2">
          <Columns3 className="mx-auto text-zinc-500" />
          <p className="text-white font-medium">Nothing to compare yet</p>
          <p className="text-zinc-400 text-sm">Press “Compare” on up to 5 products in Daily Winners or on a product report.</p>
          <Link href="/dashboard/winners" className="inline-block mt-2 px-4 py-2 rounded-lg bg-violet-600 text-white text-sm hover:bg-violet-500">Go to Daily Winners</Link>
        </div>
      ) : err ? (
        <div className={cn("rounded-xl p-4 text-sm", err.code ? "bg-zinc-900 border border-zinc-800 text-zinc-300" : "bg-red-500/10 border border-red-500/20 text-red-300")}>
          {err.code && <Lock size={14} className="inline mr-1.5 text-violet-300" />}{err.message}{" "}
          {err.code && <Link href="/dashboard/billing" className="text-violet-300 underline">See plans</Link>}
        </div>
      ) : isLoading || !data ? (
        <div className="h-96 bg-zinc-900 border border-zinc-800 rounded-xl animate-pulse" />
      ) : (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-x-auto">
          <table className="w-full text-sm min-w-[640px]">
            <thead>
              <tr>
                <th className="sticky left-0 bg-zinc-900 w-44 p-3" />
                {data.items.map((i) => (
                  <th key={i.id} className="p-3 align-top text-left font-normal min-w-[150px]">
                    <div className="space-y-2">
                      <div className="flex items-start justify-between gap-2">
                        <div className="w-14 h-14 rounded-lg bg-zinc-800 overflow-hidden shrink-0">
                          <ProductImage src={i.image_url} alt={i.title} className="w-full h-full object-cover"
                            fallback={<div className="w-full h-full flex items-center justify-center text-zinc-500"><ImageOff size={14} /></div>} />
                        </div>
                        {i.score != null && <ScoreRing score={i.score} size={44} stroke={4} />}
                      </div>
                      <Link href={`/dashboard/winners/${i.id}?market=${data.market}`} className="text-white font-medium text-sm hover:text-violet-200 line-clamp-2">{i.title}</Link>
                      <button onClick={() => toggle(i.id)} className="flex items-center gap-1 text-[11px] text-zinc-500 hover:text-white py-1">
                        <X size={11} /> Remove
                      </button>
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const best = row.best?.(data.items) ?? null;
                return (
                  <tr key={row.label} className="border-t border-zinc-800">
                    <th scope="row" className="sticky left-0 bg-zinc-900 p-3 text-left text-xs font-normal text-zinc-400">{row.label}</th>
                    {data.items.map((i) => (
                      <td key={i.id} className={cn("p-3 text-zinc-200", best === i.id && "bg-emerald-500/5 text-emerald-300")}>{row.render(i)}</td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="text-[11px] text-zinc-500 p-3 border-t border-zinc-800">
            Economics use the same labelled assumptions for every product ($5 shipping, $0.50 packaging, 3% + $0.30 fees, 5% returns).
            Your plan compares up to {data.max} products.
          </p>
        </div>
      )}
    </div>
  );
}

export default function ComparePage() {
  return (
    <div className="flex flex-col min-h-full">
      <Topbar title="Compare" />
      <Suspense fallback={null}><CompareInner /></Suspense>
    </div>
  );
}
