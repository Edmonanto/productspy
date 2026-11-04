"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight, Clock, Lightbulb, Lock, Store } from "lucide-react";
import { CriteriaRadar, ProductVisual, TrendIcon } from "@/components/visual/Visuals";
import type { Breakdown } from "@/lib/api";
import { cn } from "@/lib/utils";
import { LANDING_COPY, type Lang, type LandingCopy } from "@/content/landing-copy";

export interface PreviewPick {
  rank: number; total: number; tier: string; trend: string; category: string | null;
  image_url: string | null; revealed: boolean;
  title?: string; price_usd?: number | null; breakdown?: Breakdown;
  stores?: number | null; days_running?: number | null;
  angle?: { angle: string; hook: string } | null;
}
export interface Preview { market: string; date: string | null; total: number; picks: PreviewPick[]; markets: string[] }

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
const FLAG: Record<string, string> = { US: "🇺🇸", UK: "🇬🇧", GB: "🇬🇧", FR: "🇫🇷", DE: "🇩🇪", CA: "🇨🇦", AU: "🇦🇺", AE: "🇦🇪", SA: "🇸🇦" };

function scoreTone(s: number) {
  return s >= 70 ? "bg-emerald-500 text-emerald-950" : s >= 55 ? "bg-amber-400 text-amber-950" : "bg-zinc-600 text-white";
}

function Hero({ p, t }: { p: PreviewPick; t: LandingCopy }) {
  return (
    <div className="col-span-2 lg:row-span-2 bg-zinc-900 border border-violet-500/40 rounded-2xl overflow-hidden ring-1 ring-violet-500/20 flex flex-col">
      <div className="relative">
        <ProductVisual src={p.image_url} alt={p.title ?? t.live.topPick} category={p.category} iconSize={56}
                       className="w-full aspect-[16/10]" />
        <span className="absolute top-3 left-3 bg-violet-600 text-white text-[11px] font-bold px-2 py-1 rounded-md">{t.live.freePick}</span>
        <span className={cn("absolute top-3 right-3 rounded-lg px-2.5 py-1 text-lg font-extrabold tabular-nums shadow", scoreTone(p.total))}>{p.total}</span>
      </div>
      <div className="p-4 grid sm:grid-cols-[1fr_200px] gap-3 flex-1">
        <div className="space-y-2 min-w-0">
          <div className="text-white font-semibold leading-snug line-clamp-2">{p.title}</div>
          <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-zinc-300">
            <TrendIcon trend={p.trend} withLabel labels={t.lang === "en" ? undefined : t.trend} />
            {p.price_usd != null && <span className="bg-zinc-800 rounded-full px-2 py-0.5">{t.lang === "fr" ? `${p.price_usd.toFixed(2).replace(".", ",")} $` : `$${p.price_usd.toFixed(2)}`}</span>}
            {!!p.stores && <span className="bg-zinc-800 rounded-full px-2 py-0.5 inline-flex items-center gap-1"><Store size={11} /> {t.live.stores(p.stores)}</span>}
            {!!p.days_running && <span className="bg-zinc-800 rounded-full px-2 py-0.5 inline-flex items-center gap-1"><Clock size={11} /> {t.live.daysAds(p.days_running)}</span>}
          </div>
          {p.angle && (
            <div className="bg-violet-500/10 border border-violet-500/20 rounded-lg p-2.5 text-xs">
              <div className="flex items-center gap-1 text-violet-300 font-semibold"><Lightbulb size={12} /> {p.angle.angle}</div>
              <div className="text-zinc-300 mt-0.5">“{p.angle.hook}”</div>
            </div>
          )}
        </div>
        {p.breakdown && Object.keys(p.breakdown).length > 0 && <CriteriaRadar breakdown={p.breakdown} size={160} labels={t.radar} />}
      </div>
    </div>
  );
}

function LockedTile({ p, t }: { p: PreviewPick; t: LandingCopy }) {
  return (
    <Link href={`/signup${t.lang === "en" ? "" : `?lang=${t.lang}`}`} className="group relative block bg-zinc-900 border border-zinc-800 hover:border-violet-500/50 rounded-xl overflow-hidden transition-colors">
      <ProductVisual src={p.image_url} alt={t.live.pick(p.rank)} category={p.category} className="w-full aspect-square [&_img]:blur-md [&_img]:scale-110" />
      <span className="absolute top-2 left-2 w-7 h-7 rounded-full bg-black/60 backdrop-blur text-white text-xs font-bold flex items-center justify-center">{p.rank}</span>
      <span className={cn("absolute top-2 right-2 rounded-lg px-2 py-0.5 text-sm font-extrabold tabular-nums shadow", scoreTone(p.total))}>{p.total}</span>
      <TrendIcon trend={p.trend} labels={t.lang === "en" ? undefined : t.trend} className="absolute bottom-2 left-2 bg-black/60 backdrop-blur" />
      <span className="absolute inset-0 flex items-center justify-center">
        <span className="flex items-center gap-1.5 bg-black/70 backdrop-blur text-white text-xs font-semibold px-3 py-1.5 rounded-full opacity-90 group-hover:opacity-100 group-hover:bg-violet-600 transition-colors">
          <Lock size={12} /> {t.live.unlock}
        </span>
      </span>
    </Link>
  );
}

function Placeholder() {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      <div className="col-span-2 row-span-2 rounded-2xl bg-zinc-900 border border-zinc-800 aspect-[4/3] lg:aspect-auto animate-pulse" />
      {Array.from({ length: 4 }).map((_, i) => <div key={i} className="rounded-xl bg-zinc-900 border border-zinc-800 aspect-square animate-pulse" />)}
    </div>
  );
}

/** Today's real picks for the chosen market — no login needed. */
export default function LivePicks({ initial, lang = "en" }: { initial: Preview | null; lang?: Lang }) {
  const t = LANDING_COPY[lang];
  const [data, setData] = useState<Preview | null>(initial);
  const [market, setMarket] = useState(initial?.market ?? t.defaultMarket);
  const [loading, setLoading] = useState(!initial);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (data && data.market === market) return;
    let off = false;
    setLoading(true);
    fetch(`${API}/winners/preview?market=${market}`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((d: Preview) => { if (!off) { setData(d); setFailed(false); } })
      .catch(() => { if (!off) setFailed(true); })
      .finally(() => { if (!off) setLoading(false); });
    return () => { off = true; };
  }, [market]); // eslint-disable-line react-hooks/exhaustive-deps

  const markets = data?.markets?.length ? data.markets : ["US", "UK", "FR"];
  const [first, ...rest] = data?.market === market ? data.picks : [];
  const hidden = Math.max(0, (data?.total ?? 0) - 1);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-sm">
          <span className="relative flex w-2.5 h-2.5"><span className="absolute inset-0 rounded-full bg-emerald-400 animate-ping opacity-60" /><span className="relative w-2.5 h-2.5 rounded-full bg-emerald-400" /></span>
          <span className="text-white font-semibold">{t.live.today}</span>
          {data?.date && <span className="text-zinc-500">· {new Date(data.date + "T00:00:00").toLocaleDateString(t.locale, { month: "short", day: "numeric" })}</span>}
        </div>
        <div className="flex gap-1 bg-zinc-900 border border-zinc-800 rounded-lg p-1" role="tablist" aria-label={t.live.market}>
          {markets.map((m) => (
            <button key={m} role="tab" aria-selected={m === market} onClick={() => setMarket(m)}
                    className={cn("px-3 py-1.5 rounded-md text-xs font-semibold transition-colors",
                                  m === market ? "bg-violet-600 text-white" : "text-zinc-400 hover:text-white")}>
              {FLAG[m] ?? ""} {m}
            </button>
          ))}
        </div>
      </div>

      {loading ? <Placeholder /> : failed || !first ? (
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-8 text-center text-sm text-zinc-400">
          {failed ? t.live.waking : t.live.running}
        </div>
      ) : (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <Hero p={first} t={t} />
          {rest.slice(0, 4).map((p) => <LockedTile key={p.rank} p={p} t={t} />)}
        </div>
      )}

      {hidden > 0 && (
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-1">
          <span className="text-zinc-400 text-sm">{t.live.more(hidden)}</span>
          <Link href={`/signup${lang === "en" ? "" : `?lang=${lang}`}`} className="inline-flex items-center gap-1.5 bg-violet-600 hover:bg-violet-500 text-white text-sm font-semibold px-4 py-2 rounded-lg">
            {t.live.seeAll} <ArrowRight size={14} />
          </Link>
        </div>
      )}
    </div>
  );
}
