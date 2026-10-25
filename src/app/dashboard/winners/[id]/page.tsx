"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import useSWR from "swr";
import {
  AlertTriangle, ArrowLeft, CheckCircle2, ExternalLink, ImageOff, Lock, Package, PlayCircle,
} from "lucide-react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import Topbar from "@/components/layout/Topbar";
import ScoreRing from "@/components/winners/ScoreRing";
import PillarBars from "@/components/winners/PillarBars";
import ProductImage from "@/components/products/ProductImage";
import ProfitCalculator from "@/components/products/ProfitCalculator";
import QuoteForm from "@/components/products/QuoteForm";
import { AdEvidence, winnersApi } from "@/lib/api";
import { cn, fmtNum, fmtPct, formatPrice, recallMarket, SOURCE_LABEL } from "@/lib/utils";

const TABS = [
  { key: "meta", label: "Facebook / Instagram ads" },
  { key: "tiktok_ads", label: "TikTok ads" },
  { key: "tiktok_organic", label: "TikTok videos" },
];

function AdCard({ ad }: { ad: AdEvidence }) {
  const metrics: string[] = [];
  if (ad.days_running != null && ad.platform !== "tiktok_organic") metrics.push(`${ad.days_running}d running`);
  if (ad.variant_count && ad.variant_count > 1) metrics.push(`${ad.variant_count} versions`);
  if (ad.reach) metrics.push(`${fmtNum(ad.reach)} reach`);
  if (ad.views) metrics.push(`${fmtNum(ad.views)} views`);
  if (ad.likes) metrics.push(`${fmtNum(ad.likes)} likes`);
  if (ad.shares) metrics.push(`${fmtNum(ad.shares)} shares`);
  if (ad.ctr) metrics.push(`${fmtPct(ad.ctr)} CTR`);
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden flex flex-col">
      <div className="aspect-video bg-zinc-800 relative">
        <ProductImage
          src={ad.thumbnail_url}
          alt={ad.advertiser_name ?? "Ad"}
          className="w-full h-full object-cover"
          fallback={<div className="w-full h-full flex items-center justify-center text-zinc-500"><ImageOff size={20} /></div>}
        />
        {ad.ad_url && (
          <a href={ad.ad_url} target="_blank" rel="noreferrer"
             aria-label={`Open the ad${ad.advertiser_name ? ` by ${ad.advertiser_name}` : ""}`}
             className="absolute inset-0 flex items-center justify-center opacity-0 hover:opacity-100 focus-visible:opacity-100 bg-black/40 transition-opacity">
            <PlayCircle className="text-white" size={32} />
          </a>
        )}
      </div>
      <div className="p-3 space-y-1.5 text-xs flex-1">
        <div className="text-zinc-200 font-medium truncate">{ad.advertiser_name ?? ad.landing_domain ?? "Unknown"}</div>
        {ad.ad_text && <p className="text-zinc-500 line-clamp-2">{ad.ad_text}</p>}
        <div className="flex flex-wrap gap-1">
          {metrics.map((m) => (
            <span key={m} className="bg-zinc-800 text-zinc-300 rounded px-1.5 py-0.5">{m}</span>
          ))}
        </div>
      </div>
      <div className="flex border-t border-zinc-800 text-xs">
        {ad.ad_url && (
          <a href={ad.ad_url} target="_blank" rel="noreferrer" className="flex-1 text-center py-2 max-md:py-3 text-zinc-400 hover:text-white hover:bg-zinc-800">
            View
          </a>
        )}
        {ad.landing_url && (
          <a href={ad.landing_url} target="_blank" rel="noreferrer" className="flex-1 text-center py-2 max-md:py-3 text-zinc-400 hover:text-white hover:bg-zinc-800 border-l border-zinc-800">
            Store
          </a>
        )}
      </div>
    </div>
  );
}

function EvidenceInner() {
  const { id } = useParams<{ id: string }>();
  const params = useSearchParams();
  const market = (params.get("market") ?? recallMarket() ?? "US").toUpperCase();
  const [tab, setTab] = useState("meta");
  const [quoteQty, setQuoteQty] = useState<number | null>(null);
  const { data, error, isLoading } = useSWR(["evidence", id, market], () => winnersApi.product(id, market));

  if (error) {
    return <div className="p-6 text-red-300 text-sm">{(error as Error).message}</div>;
  }
  if (isLoading || !data) {
    return (
      <div className="p-6 space-y-4 animate-pulse max-w-6xl mx-auto w-full">
        <div className="h-8 w-64 bg-zinc-800 rounded" />
        <div className="h-64 bg-zinc-900 rounded-xl" />
      </div>
    );
  }

  const { product: p, score } = data;
  const mult = p.price_usd && p.cost_usd ? p.price_usd / p.cost_usd : null;
  const profit = p.price_usd && p.cost_usd ? p.price_usd - p.cost_usd : null;
  const firstTabWithAds = TABS.find((t) => (data.ads[t.key] ?? []).length)?.key;
  const activeTab = (data.ads[tab] ?? []).length ? tab : firstTabWithAds ?? tab;

  return (
    <div className="p-4 md:p-6 max-w-6xl mx-auto w-full space-y-5">
      <Link href={`/dashboard/winners?market=${market}`} className="py-3 -my-3 inline-flex items-center gap-1 text-xs text-zinc-500 hover:text-white">
        <ArrowLeft size={12} /> Back to winners
      </Link>

      {/* Header */}
      <div className="grid md:grid-cols-[180px_1fr] lg:grid-cols-[220px_1fr_260px] gap-5 bg-zinc-900 border border-zinc-800 rounded-xl p-4 md:p-5">
        <div className="h-48 sm:h-64 md:h-auto md:aspect-square bg-zinc-800 rounded-lg overflow-hidden">
          <ProductImage
            src={p.image_url}
            alt={p.title}
            className="w-full h-full object-cover"
            fallback={<div className="w-full h-full flex items-center justify-center text-zinc-500"><Package size={28} /></div>}
          />
        </div>
        <div className="space-y-3 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h2 className="text-white text-lg md:text-xl font-semibold">{p.title}</h2>
          </div>
          <div className="text-xs text-zinc-500 capitalize">
            {p.category ? `${p.category.replace("-", " ")} · ` : ""}{market}
            {p.first_seen_at && <> · first seen {new Date(p.first_seen_at).toLocaleDateString()}</>}
          </div>
          {score && (
            <ul className="space-y-1.5">
              {score.reasons.map((r) => (
                <li key={r} className="flex gap-2 text-sm text-zinc-300">
                  <CheckCircle2 size={15} className="text-emerald-400 mt-0.5 shrink-0" /> {r}
                </li>
              ))}
              {score.penalties.map((pen) => (
                <li key={pen.reason} className="flex gap-2 text-sm text-zinc-400">
                  <AlertTriangle size={15} className="text-amber-400 mt-0.5 shrink-0" /> {pen.reason} (−{pen.points})
                </li>
              ))}
              {score.excluded && (
                <li className="flex gap-2 text-sm text-red-300">
                  <AlertTriangle size={15} className="mt-0.5 shrink-0" /> Excluded: {score.excluded}
                </li>
              )}
            </ul>
          )}
        </div>
        <div className="space-y-4 md:col-span-2 lg:col-span-1 lg:border-l lg:border-zinc-800 lg:pl-5">
          {score && (
            <>
              <div className="flex items-center gap-3">
                <ScoreRing score={score.total} size={80} stroke={7} />
                <div className="text-xs text-zinc-400">
                  <div className="capitalize">{score.confidence} confidence</div>
                  <div className="text-zinc-500">scored {score.scored_on}</div>
                </div>
              </div>
              <PillarBars breakdown={score.breakdown} />
            </>
          )}
        </div>
      </div>

      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* Unit economics */}
        <div className="md:col-span-2 lg:col-span-1 bg-zinc-900 border border-zinc-800 rounded-xl p-4 md:p-5 space-y-3">
          <h3 className="text-white text-sm font-semibold">Unit economics</h3>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="bg-zinc-800/60 rounded-lg py-3">
              <div className="text-[11px] text-zinc-500">Sell price</div>
              <div className="text-white font-semibold">{formatPrice(p.price_usd)}</div>
            </div>
            <div className="bg-zinc-800/60 rounded-lg py-3">
              <div className="text-[11px] text-zinc-500">Cost{p.cost_estimated && " (est.)"}</div>
              <div className="text-white font-semibold">{formatPrice(p.cost_usd)}</div>
            </div>
            <div className="bg-zinc-800/60 rounded-lg py-3">
              <div className="text-[11px] text-zinc-500">Markup</div>
              <div className={cn("font-semibold", mult && mult >= 3 ? "text-emerald-400" : "text-amber-300")}>
                {mult ? `${mult.toFixed(1)}×` : "—"}
              </div>
            </div>
          </div>
          {profit != null && (
            <p className="text-xs text-zinc-500">
              ≈ {formatPrice(profit)} gross profit per order before ads & fees.
              {p.cost_estimated && " Cost is an AI estimate — confirm with your supplier."}
            </p>
          )}
          {data.suppliers.length > 0 && (
            <div className="space-y-1.5 pt-1">
              {data.suppliers.map((s) => (
                <a key={s.supplier_url} href={s.supplier_url} target="_blank" rel="noreferrer"
                   className="flex items-center justify-between gap-2 text-xs bg-zinc-800/60 hover:bg-zinc-800 rounded-lg px-3 py-2 max-md:min-h-[44px]">
                  <span className="text-zinc-300">{s.supplier_name}</span>
                  <span className="flex items-center gap-1 text-zinc-400">
                    {formatPrice(s.unit_cost_usd)} <ExternalLink size={11} />
                  </span>
                </a>
              ))}
            </div>
          )}
        </div>

        {/* Score history */}
        <div className="md:col-span-2 bg-zinc-900 border border-zinc-800 rounded-xl p-4 md:p-5">
          <h3 className="text-white text-sm font-semibold mb-3">Score over time</h3>
          {data.history.length > 1 ? (
            <div className="h-40">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={data.history} margin={{ left: -20, right: 8, top: 4, bottom: 0 }}>
                  <XAxis dataKey="date" tick={{ fill: "#71717a", fontSize: 11 }} tickLine={false} axisLine={false} />
                  <YAxis domain={[0, 100]} tick={{ fill: "#71717a", fontSize: 11 }} tickLine={false} axisLine={false} />
                  <Tooltip contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", fontSize: 12 }} />
                  <Line type="monotone" dataKey="total" stroke="#a78bfa" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <p className="text-zinc-500 text-sm">History builds up as the daily scan re-scores this product.</p>
          )}
        </div>
      </div>

      {/* Profit + sourcing quote */}
      <ProfitCalculator
        key={p.id}
        priceUsd={p.price_usd}
        costUsd={p.cost_usd}
        costEstimated={p.cost_estimated}
        onRequestQuote={setQuoteQty}
      />
      <QuoteForm
        productId={p.id}
        productTitle={p.title}
        initialQuantity={quoteQty ?? 100}
        open={quoteQty != null}
        onClose={() => setQuoteQty(null)}
      />

      {/* Evidence */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 md:p-5 space-y-4">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <h3 className="text-white text-sm font-semibold">Evidence</h3>
          <div className="flex gap-1 overflow-x-auto -mx-1 px-1 max-w-full">
            {TABS.filter((t) => t.key === activeTab || (data.ad_counts[t.key] ?? 0) > 0).map((t) => (
              <button key={t.key} onClick={() => setTab(t.key)}
                      className={cn("px-3 py-2 md:py-1.5 max-md:min-h-[44px] rounded-lg text-xs whitespace-nowrap shrink-0",
                        activeTab === t.key ? "bg-zinc-800 text-white" : "text-zinc-500 hover:text-white")}>
                {t.label} <span className="text-zinc-500">{data.ad_counts[t.key] ?? 0}</span>
              </button>
            ))}
          </div>
        </div>
        {data.ad_evidence_locked ? (
          <div className="text-center py-10 space-y-2">
            <Lock className="mx-auto text-violet-300" />
            <p className="text-zinc-300 text-sm">
              {Object.values(data.ad_counts).reduce((a, b) => a + b, 0)} ads & videos found for this product.
            </p>
            <Link href="/dashboard/billing" className="inline-block px-4 py-2 rounded-lg bg-violet-600 text-white text-sm hover:bg-violet-500">
              Upgrade to see them
            </Link>
          </div>
        ) : (data.ads[activeTab] ?? []).length === 0 ? (
          <p className="text-zinc-500 text-sm py-6 text-center">Nothing from {SOURCE_LABEL[activeTab]} for this product yet.</p>
        ) : (
          <div className="grid grid-cols-1 min-[420px]:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            {data.ads[activeTab].map((ad, i) => <AdCard key={`${ad.ad_url}-${i}`} ad={ad} />)}
          </div>
        )}
      </div>
    </div>
  );
}

export default function EvidencePage() {
  return (
    <div className="flex flex-col min-h-full">
      <Topbar title="Product evidence" />
      <Suspense fallback={null}>
        <EvidenceInner />
      </Suspense>
    </div>
  );
}
