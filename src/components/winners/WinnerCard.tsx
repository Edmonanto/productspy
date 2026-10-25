"use client";

import Link from "next/link";
import { useState } from "react";
import {
  ArrowRight, Bookmark, CheckCircle2, Clock, ExternalLink, Layers, Store,
  TrendingUp, MessageCircle, AlertTriangle, Lock, ImageOff,
} from "lucide-react";
import { WinnerPick, watchlistApi } from "@/lib/api";
import { cn, fmtNum, fmtPct, formatPrice, SOURCE_LABEL } from "@/lib/utils";
import ScoreRing from "./ScoreRing";
import PillarBars from "./PillarBars";
import ProductImage from "@/components/products/ProductImage";

function Stat({ icon: Icon, label, value }: { icon: typeof Clock; label: string; value: string }) {
  return (
    <div className="flex items-center gap-1.5 bg-zinc-800/60 border border-zinc-800 rounded-md px-2 py-1">
      <Icon size={12} className="text-zinc-500" />
      <span className="text-zinc-200 text-xs font-semibold tabular-nums">{value}</span>
      <span className="text-zinc-500 text-[11px]">{label}</span>
    </div>
  );
}

export function LockedWinnerCard({ pick }: { pick: WinnerPick }) {
  return (
    <div className="relative bg-zinc-900 border border-zinc-800 rounded-xl p-4 overflow-hidden">
      <div className="flex items-center gap-4 blur-[3px] select-none opacity-50" aria-hidden>
        <div className="w-20 h-20 rounded-lg bg-zinc-800" />
        <div className="flex-1 space-y-2">
          <div className="h-4 w-1/2 bg-zinc-700 rounded" />
          <div className="h-3 w-3/4 bg-zinc-800 rounded" />
          <div className="h-3 w-2/3 bg-zinc-800 rounded" />
        </div>
        <ScoreRing score={pick.total} size={56} />
      </div>
      <Link
        href="/dashboard/billing"
        className="absolute inset-0 flex items-center justify-center gap-2 text-sm font-medium text-white bg-zinc-950/40 hover:bg-zinc-950/30 transition-colors"
      >
        <Lock size={14} className="text-violet-300" />
        Winner #{pick.rank} (score {pick.total}) — upgrade to unlock
      </Link>
    </div>
  );
}

export default function WinnerCard({ pick, market }: { pick: WinnerPick; market: string }) {
  const [saved, setSaved] = useState(false);
  const p = pick.product!;
  const s = pick.stats!;
  const mult = p.price_usd && p.cost_usd ? p.price_usd / p.cost_usd : null;
  const href = `/dashboard/winners/${p.id}?market=${market}`;

  const toggleSave = async () => {
    try {
      if (saved) await watchlistApi.remove(p.id);
      else await watchlistApi.add(p.id);
      setSaved(!saved);
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <article className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden hover:border-zinc-700 transition-colors">
      <div className="flex flex-col md:flex-row gap-4 p-4">
        {/* Image + rank */}
        <Link href={href} className="relative shrink-0 self-start">
          <div className="w-24 md:w-32 aspect-square rounded-lg bg-zinc-800 overflow-hidden">
            <ProductImage
              src={p.image_url}
              alt={p.title}
              className="w-full h-full object-cover"
              fallback={<div className="w-full h-full flex items-center justify-center text-zinc-600"><ImageOff size={20} /></div>}
            />
          </div>
          <span className="absolute -top-2 -left-2 w-8 h-8 rounded-full bg-zinc-950 border border-zinc-700 flex items-center justify-center text-white text-sm font-bold">
            {pick.rank}
          </span>
        </Link>

        {/* Main */}
        <div className="flex-1 min-w-0 space-y-3">
          <div className="flex items-start gap-2 flex-wrap">
            <Link href={href} className="text-white font-semibold text-base hover:text-violet-200 leading-snug">
              {p.title}
            </Link>
            {pick.tier === "rising" && (
              <span className="text-[10px] font-semibold uppercase tracking-wide bg-amber-500/15 text-amber-300 border border-amber-500/30 rounded px-1.5 py-0.5">
                Rising
              </span>
            )}
          </div>

          <div className="flex items-center gap-2 text-xs text-zinc-500 flex-wrap">
            {p.category && <span className="capitalize">{p.category.replace("-", " ")}</span>}
            {s.sources.map((src) => (
              <span key={src} className="bg-zinc-800 text-zinc-300 rounded px-1.5 py-0.5">
                {SOURCE_LABEL[src] ?? src}
              </span>
            ))}
            {pick.confidence && (
              <span className={cn(
                "rounded px-1.5 py-0.5",
                pick.confidence === "high" ? "text-emerald-300 bg-emerald-500/10"
                  : pick.confidence === "medium" ? "text-amber-300 bg-amber-500/10" : "text-zinc-400 bg-zinc-800"
              )}>
                {pick.confidence} confidence
              </span>
            )}
          </div>

          {/* Why it's a winner */}
          <ul className="space-y-1">
            {(pick.reasons ?? []).slice(0, 4).map((r) => (
              <li key={r} className="flex items-start gap-2 text-sm text-zinc-300">
                <CheckCircle2 size={14} className="text-emerald-400 mt-0.5 shrink-0" />
                <span>{r}</span>
              </li>
            ))}
            {(pick.penalties ?? []).slice(0, 2).map((pen) => (
              <li key={pen.reason} className="flex items-start gap-2 text-sm text-zinc-400">
                <AlertTriangle size={14} className="text-amber-400 mt-0.5 shrink-0" />
                <span>{pen.reason} <span className="text-zinc-600">(−{pen.points})</span></span>
              </li>
            ))}
          </ul>

          <div className="flex flex-wrap gap-1.5">
            {s.days_running != null && <Stat icon={Clock} label="days running" value={String(s.days_running)} />}
            {!!s.creatives && <Stat icon={Layers} label="ads" value={String(s.creatives)} />}
            {!!s.stores && <Stat icon={Store} label="stores" value={String(s.stores)} />}
            {!!s.views && <Stat icon={TrendingUp} label="views" value={fmtNum(s.views)} />}
            {s.engagement_rate != null && <Stat icon={MessageCircle} label="engagement" value={fmtPct(s.engagement_rate)} />}
          </div>
        </div>

        {/* Score */}
        <div className="md:w-60 shrink-0 space-y-3 md:border-l md:border-zinc-800 md:pl-4">
          <div className="flex items-center gap-3">
            <ScoreRing score={pick.total} />
            <div className="text-xs space-y-0.5">
              <div className="text-zinc-500">Sell price</div>
              <div className="text-white font-semibold">{formatPrice(p.price_usd)}</div>
              {mult && (
                <div className="text-emerald-400 font-medium">
                  {mult.toFixed(1)}× cost{p.cost_estimated && <span className="text-zinc-500"> (est.)</span>}
                </div>
              )}
            </div>
          </div>
          {pick.breakdown && <PillarBars breakdown={pick.breakdown} compact />}
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1 border-t border-zinc-800 px-4 py-2 text-xs flex-wrap">
        {pick.links?.ad_url && (
          <a href={pick.links.ad_url} target="_blank" rel="noreferrer"
             className="flex items-center gap-1 px-2.5 py-1.5 rounded-md text-zinc-400 hover:text-white hover:bg-zinc-800">
            <ExternalLink size={12} /> See ad
          </a>
        )}
        {pick.links?.store_url && (
          <a href={pick.links.store_url} target="_blank" rel="noreferrer"
             className="flex items-center gap-1 px-2.5 py-1.5 rounded-md text-zinc-400 hover:text-white hover:bg-zinc-800">
            <Store size={12} /> Competitor store
          </a>
        )}
        {pick.links?.supplier_url && (
          <a href={pick.links.supplier_url} target="_blank" rel="noreferrer"
             className="flex items-center gap-1 px-2.5 py-1.5 rounded-md text-zinc-400 hover:text-white hover:bg-zinc-800">
            <ExternalLink size={12} /> Supplier
          </a>
        )}
        <button onClick={toggleSave}
                className={cn("flex items-center gap-1 px-2.5 py-1.5 rounded-md hover:bg-zinc-800",
                  saved ? "text-violet-300" : "text-zinc-400 hover:text-white")}>
          <Bookmark size={12} fill={saved ? "currentColor" : "none"} /> {saved ? "Saved" : "Save"}
        </button>
        <Link href={href} className="ml-auto flex items-center gap-1 px-2.5 py-1.5 rounded-md text-violet-300 hover:text-violet-200 hover:bg-violet-500/10 font-medium">
          Full evidence <ArrowRight size={12} />
        </Link>
      </div>
    </article>
  );
}
