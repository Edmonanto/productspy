"use client";

import { Suspense } from "react";
import Link from "next/link";
import useSWR from "swr";
import {
  ArrowRight, Award, Bookmark, Clock, Percent, ScanSearch, Store, Trophy,
} from "lucide-react";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import Topbar from "@/components/layout/Topbar";
import MarketPicker from "@/components/winners/MarketPicker";
import ScoreRing from "@/components/winners/ScoreRing";
import { Chip, CriteriaRadar, PickTile, ProductVisual, TrendIcon } from "@/components/visual/Visuals";
import OpportunityMap, { TrendLegend } from "@/components/visual/OpportunityMap";
import { usersApi, watchlistApi, winnersApi, Me, WinnerPick } from "@/lib/api";
import { useMarket } from "@/lib/useMarket";
import { cn, TREND } from "@/lib/utils";

const TREND_COLOR: Record<string, string> = {
  emerging: "#38bdf8", growing: "#34d399", stable: "#a1a1aa", declining: "#f87171", seasonal: "#fbbf24", unknown: "#52525b",
};

function Kpi({ icon: Icon, value, label, tone }: { icon: typeof Trophy; value: React.ReactNode; label: string; tone: string }) {
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 flex items-center gap-3">
      <div className={cn("w-10 h-10 rounded-xl flex items-center justify-center shrink-0", tone)}><Icon size={18} /></div>
      <div className="min-w-0">
        <div className="text-2xl font-extrabold text-white tabular-nums leading-none">{value}</div>
        <div className="text-[11px] text-zinc-400 mt-1">{label}</div>
      </div>
    </div>
  );
}

function Panel({ title, action, children, className }: { title: string; action?: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <section className={cn("bg-zinc-900 border border-zinc-800 rounded-xl p-4", className)}>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-white font-semibold text-sm">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

function Hero({ pick, market }: { pick: WinnerPick; market: string }) {
  const p = pick.product!;
  const margin = pick.economics?.complete ? pick.economics.contribution_margin_pct : null;
  return (
    <Link href={`/dashboard/winners/${p.id}?market=${market}`}
          className="group grid sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-4 bg-gradient-to-br from-violet-950/60 via-zinc-900 to-zinc-900 border border-violet-800/30 hover:border-violet-500/50 rounded-2xl p-4 transition-colors">
      <div className="relative">
        <ProductVisual src={p.image_url} alt={p.title} category={p.category} iconSize={56} className="w-full aspect-[4/3] rounded-xl" />
        <span className="absolute top-2 left-2 inline-flex items-center gap-1 bg-amber-400 text-amber-950 text-[11px] font-bold rounded-full px-2 py-1">
          <Trophy size={12} /> #1 today
        </span>
      </div>
      <div className="flex flex-col min-w-0">
        <div className="flex items-start gap-3">
          <ScoreRing score={pick.total} size={64} stroke={6} />
          <div className="min-w-0">
            <h3 className="text-white font-semibold text-lg leading-snug line-clamp-2 group-hover:text-violet-100">{p.title}</h3>
            <div className="mt-1.5 flex flex-wrap gap-1">
              <TrendIcon trend={pick.trend} withLabel />
              {p.price_usd != null && <Chip icon={Store} value={`$${p.price_usd.toFixed(2)}`} title="Competitor price" />}
              {margin != null && <Chip icon={Percent} value={`${Math.round(margin)}%`} title="Margin before ads" tone="text-emerald-300" />}
              {pick.stats?.days_running != null && <Chip icon={Clock} value={`${pick.stats.days_running}d`} title="Longest-running ad" />}
            </div>
          </div>
        </div>
        <div className="flex-1 min-h-[170px] -mx-2"><CriteriaRadar breakdown={pick.breakdown} size={190} compact /></div>
        <span className="self-end inline-flex items-center gap-1 text-xs text-violet-300 font-medium">Open research <ArrowRight size={12} /></span>
      </div>
    </Link>
  );
}

function TrendMix({ picks }: { picks: WinnerPick[] }) {
  const counts = picks.reduce<Record<string, number>>((a, w) => { const t = w.trend ?? "unknown"; a[t] = (a[t] ?? 0) + 1; return a; }, {});
  const data = Object.entries(counts).map(([t, n]) => ({ t, n, name: TREND[t]?.label ?? t }));
  if (!data.length) return <p className="text-zinc-500 text-xs">—</p>;
  return (
    <div className="flex items-center gap-3">
      <div className="w-28 h-28 shrink-0" role="img" aria-label={data.map((d) => `${d.name}: ${d.n}`).join(", ")}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={data} dataKey="n" nameKey="name" innerRadius="58%" outerRadius="95%" paddingAngle={2} stroke="none" isAnimationActive={false}>
              {data.map((d) => <Cell key={d.t} fill={TREND_COLOR[d.t] ?? "#52525b"} />)}
            </Pie>
            <Tooltip contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", fontSize: 12 }} />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <ul className="space-y-1 text-xs">
        {data.sort((a, b) => b.n - a.n).map((d) => (
          <li key={d.t} className="flex items-center gap-2 text-zinc-300">
            <span className="w-2 h-2 rounded-full" style={{ background: TREND_COLOR[d.t] }} /> {d.name}
            <span className="text-zinc-500 tabular-nums">{d.n}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function OverviewInner() {
  const { data: me } = useSWR<Me>("me", usersApi.me);
  const { market, setMarket, meta } = useMarket();
  const { data: winners, isLoading } = useSWR(market ? ["winners", market, undefined] : null, () => winnersApi.list(market!));
  const { data: watch } = useSWR("watchlist", watchlistApi.list);
  const { data: status } = useSWR("winner-status", winnersApi.status, { refreshInterval: 60_000 });

  const picks = (winners?.winners ?? []).filter((w) => !w.locked && w.product);
  const top = picks[0];
  const nWinners = picks.filter((w) => w.tier === "winner").length;
  const margins = picks.map((w) => w.economics?.contribution_margin_pct).filter((m): m is number => m != null);
  const avgMargin = margins.length ? Math.round(margins.reduce((a, b) => a + b, 0) / margins.length) : null;
  const run = status?.runs.find((r) => r.market === market);
  const nameOf = (c: string) => meta.data?.markets.find((m) => m.code === c);
  const saved = watch?.items ?? [];

  return (
    <div className="flex flex-col min-h-full">
      <Topbar title="Overview" />
      <div className="p-4 sm:p-6 space-y-5 flex-1 max-w-6xl w-full mx-auto">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <h1 className="text-white text-xl font-semibold">Hi {me?.name?.split(" ")[0] ?? ""} 👋</h1>
          {meta.data && market && (
            <MarketPicker markets={meta.data.markets}
              following={meta.data.following.includes(market) ? meta.data.following : [...meta.data.following, market]}
              value={market} onChange={setMarket} />
          )}
        </div>

        {/* Hero + KPIs */}
        <div className="grid lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2">
            {isLoading || !market ? <div className="h-72 bg-zinc-900 border border-zinc-800 rounded-2xl animate-pulse" />
              : top ? <Hero pick={top} market={market} />
              : (
                <div className="h-full min-h-[200px] bg-zinc-900 border border-zinc-800 rounded-2xl flex flex-col items-center justify-center gap-2 text-center p-6">
                  <ScanSearch className="text-zinc-500" size={32} />
                  <p className="text-zinc-300 text-sm">First scan on its way</p>
                </div>
              )}
          </div>
          <div className="grid grid-cols-2 lg:grid-cols-1 gap-3 content-start">
            <Kpi icon={Trophy} value={picks.length || "—"} label="Picks today" tone="bg-violet-600/20 text-violet-300" />
            <Kpi icon={Award} value={nWinners} label="Strong (70+)" tone="bg-emerald-600/20 text-emerald-300" />
            <Kpi icon={Percent} value={avgMargin != null ? `${avgMargin}%` : "—"} label="Avg margin" tone="bg-amber-500/20 text-amber-300" />
            <Kpi icon={ScanSearch} value={run?.stats?.scored ?? "—"} label="Products scanned" tone="bg-sky-600/20 text-sky-300" />
          </div>
        </div>

        {/* Gallery */}
        {picks.length > 1 && (
          <Panel title="Today's picks"
                 action={<Link href={`/dashboard/winners?market=${market}`} className="text-xs text-violet-300 hover:text-violet-200 inline-flex items-center gap-1 py-2 -my-2">All <ArrowRight size={12} /></Link>}>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
              {picks.slice(1, 11).map((w) => <PickTile key={w.rank} pick={w} market={market!} />)}
            </div>
          </Panel>
        )}

        {/* Charts */}
        <div className="grid lg:grid-cols-3 gap-4">
          <Panel title="Opportunity map" className="lg:col-span-2" action={<TrendLegend />}>
            <div className="flex">
              <span className="text-[10px] text-zinc-500 [writing-mode:vertical-rl] rotate-180 self-center mr-1">score ↑</span>
              <div className="flex-1 min-w-0">{market && <OpportunityMap picks={picks} market={market} />}</div>
            </div>
            <div className="text-[10px] text-zinc-500 text-center">margin before ads →</div>
          </Panel>
          <div className="space-y-4">
            <Panel title="Trends"><TrendMix picks={picks} /></Panel>
            <Panel title="Daily scan">
              {status?.runs.length ? (
                <div className="flex flex-wrap gap-2">
                  {status.runs.map((r) => (
                    <span key={r.market} title={`${r.status} · ${r.stats?.scored ?? 0} scored`}
                          className="inline-flex items-center gap-1.5 bg-zinc-800/70 rounded-full pl-2 pr-2.5 py-1 text-xs text-zinc-200">
                      <span className={cn("w-2 h-2 rounded-full", r.status === "ok" ? "bg-emerald-500" : r.status === "running" ? "bg-sky-400 animate-pulse" : r.status === "partial" ? "bg-amber-400" : "bg-red-500")} />
                      {nameOf(r.market)?.flag} <span className="tabular-nums text-zinc-400">{r.stats?.scored ?? 0}</span>
                    </span>
                  ))}
                </div>
              ) : <p className="text-zinc-500 text-xs">—</p>}
            </Panel>
          </div>
        </div>

        {/* Watchlist */}
        <Panel title="Saved"
               action={<Link href="/dashboard/watchlist" className="text-xs text-violet-300 hover:text-violet-200 inline-flex items-center gap-1 py-2 -my-2">All <ArrowRight size={12} /></Link>}>
          {saved.length ? (
            <div className="flex gap-3 overflow-x-auto pb-1 -mx-1 px-1">
              {saved.slice(0, 12).map(({ id: wid, product }) => (
                <Link key={wid} href={`/dashboard/winners/${product.id}${product.market ? `?market=${product.market}` : ""}`}
                      className="shrink-0 w-24 group" title={product.title}>
                  <div className="relative">
                    <ProductVisual src={product.image_url} alt={product.title} category={product.category} className="w-24 h-24 rounded-lg" iconSize={24} />
                    {product.score != null && (
                      <span className={cn("absolute top-1 right-1 rounded px-1.5 text-[11px] font-bold",
                        product.score >= 70 ? "bg-emerald-500 text-emerald-950" : product.score >= 55 ? "bg-amber-400 text-amber-950" : "bg-zinc-600 text-white")}>
                        {product.score}
                      </span>
                    )}
                  </div>
                  <div className="text-[11px] text-zinc-400 group-hover:text-white truncate mt-1">{product.title}</div>
                </Link>
              ))}
            </div>
          ) : (
            <Link href={`/dashboard/winners${market ? `?market=${market}` : ""}`} className="flex items-center gap-3 text-sm text-zinc-400 hover:text-white">
              <Bookmark size={18} className="text-zinc-600" /> Save products to track them here
            </Link>
          )}
        </Panel>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  return <Suspense fallback={null}><OverviewInner /></Suspense>;
}
