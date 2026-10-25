"use client";

import { Suspense } from "react";
import Link from "next/link";
import useSWR from "swr";
import { Activity, ArrowRight, Bookmark, Globe2, ImageOff, Trophy, TrendingUp } from "lucide-react";
import Topbar from "@/components/layout/Topbar";
import StatCard from "@/components/dashboard/StatCard";
import WatchlistMini from "@/components/dashboard/WatchlistMini";
import ProductImage from "@/components/products/ProductImage";
import ScoreRing from "@/components/winners/ScoreRing";
import { usersApi, watchlistApi, winnersApi, Me, WatchlistItem } from "@/lib/api";
import { useMarket } from "@/lib/useMarket";
import { formatPrice } from "@/lib/utils";

function timeAgo(iso: string | null): string {
  if (!iso) return "—";
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 60) return `${mins}m ago`;
  if (mins < 60 * 24) return `${Math.round(mins / 60)}h ago`;
  return `${Math.round(mins / 1440)}d ago`;
}

function OverviewInner() {
  const { data: me } = useSWR<Me>("me", usersApi.me);
  const { market, meta } = useMarket();
  const { data: winners, isLoading } = useSWR(market ? ["winners", market, undefined] : null, () =>
    winnersApi.list(market!)
  );
  const { data: watchlistData, isLoading: watchlistLoading } = useSWR("watchlist", watchlistApi.list);
  const { data: status } = useSWR("winner-status", winnersApi.status, { refreshInterval: 60_000 });

  const picks = (winners?.winners ?? []).filter((w) => !w.locked);
  const top = picks[0];
  const watchlistItems: WatchlistItem[] = watchlistData?.items ?? [];
  const followed = meta.data?.following ?? [];
  const nameOf = (c: string) => meta.data?.markets.find((m) => m.code === c);
  const winnersToday = winners?.winners.filter((w) => w.tier === "winner").length;

  return (
    <div className="flex flex-col min-h-full">
      <Topbar title="Overview" />
      <div className="p-4 sm:p-6 space-y-6 flex-1 max-w-6xl w-full mx-auto">
        <div className="bg-gradient-to-r from-violet-900/30 to-indigo-900/20 border border-violet-800/30 rounded-xl px-5 py-4 flex items-center justify-between gap-3">
          <div>
            <p className="text-white font-semibold text-sm">
              Hi <span className="text-violet-300">{me?.name ?? "…"}</span>
            </p>
            <p className="text-zinc-400 text-xs mt-0.5">
              {winners?.date
                ? `Latest scan: ${winners.winners.length} products worth testing in ${nameOf(market!)?.name ?? market}.`
                : "Your first daily scan is on its way — winners appear here every morning."}
            </p>
          </div>
          <span className="text-xs font-bold px-3 py-1.5 rounded-full capitalize border bg-zinc-900/60 text-zinc-300 border-zinc-700 shrink-0">
            {me?.trial?.active ? `${me.subscription.plan} trial` : `${me?.subscription.plan ?? "free"} plan`}
          </span>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard label="Winners today" value={winnersToday ?? "—"} sub="Scored 70 or more" icon={Trophy} accent="violet" />
          <StatCard label="Top score" value={top?.total ?? "—"} sub={top?.product?.title ?? "No picks yet"} icon={TrendingUp} accent="emerald" />
          <StatCard label="Markets" value={followed.length || "—"}
                    sub={followed.map((c) => nameOf(c)?.flag ?? c).join(" ") || "Pick in Settings"} icon={Globe2} accent="blue" />
          <StatCard label="Watchlist" value={watchlistItems.length} sub="saved products" icon={Bookmark} accent="yellow" />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 bg-zinc-900 border border-zinc-800 rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-white font-semibold text-sm">Today&apos;s top picks</h3>
              <Link href={`/dashboard/winners${market ? `?market=${market}` : ""}`}
                    className="text-xs text-violet-400 hover:text-violet-300 flex items-center gap-1">
                See all <ArrowRight size={12} />
              </Link>
            </div>
            {isLoading || !market ? (
              <div className="space-y-2">
                {Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-14 bg-zinc-800/60 rounded-lg animate-pulse" />)}
              </div>
            ) : picks.length === 0 ? (
              <p className="text-zinc-500 text-sm py-8 text-center">No picks yet for this market.</p>
            ) : (
              <ul className="divide-y divide-zinc-800">
                {picks.slice(0, 5).map((w) => (
                  <li key={w.rank}>
                    <Link href={`/dashboard/winners/${w.product!.id}?market=${market}`}
                          className="flex items-center gap-3 py-2.5 hover:bg-zinc-800/40 rounded-lg px-2 -mx-2">
                      <span className="w-5 text-zinc-500 text-xs font-bold">{w.rank}</span>
                      <div className="w-10 h-10 rounded-md bg-zinc-800 overflow-hidden shrink-0">
                        <ProductImage
                          src={w.product!.image_url}
                          alt={w.product!.title}
                          className="w-full h-full object-cover"
                          fallback={<div className="w-full h-full flex items-center justify-center text-zinc-600"><ImageOff size={14} /></div>}
                        />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm text-zinc-200 truncate">{w.product!.title}</div>
                        <div className="text-xs text-zinc-500 truncate">{w.reasons?.[0]}</div>
                      </div>
                      <span className="text-xs text-zinc-400 hidden sm:block">{formatPrice(w.product!.price_usd)}</span>
                      <ScoreRing score={w.total} size={40} stroke={4} />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="space-y-4">
            <WatchlistMini items={watchlistItems} loading={watchlistLoading} />
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
              <h3 className="text-white font-semibold text-sm mb-3 flex items-center gap-2"><Activity size={14} /> Daily scan</h3>
              {status?.runs.length ? (
                <div className="space-y-2.5">
                  {status.runs.map((r) => (
                    <div key={r.market} className="flex items-center justify-between text-xs">
                      <div className="flex items-center gap-2">
                        <span className={`w-1.5 h-1.5 rounded-full ${r.status === "ok" ? "bg-emerald-500" : r.status === "running" ? "bg-sky-400 animate-pulse" : r.status === "partial" ? "bg-amber-400" : "bg-red-500"}`} />
                        <span className="text-zinc-300">{nameOf(r.market)?.flag} {r.market}</span>
                        <span className="text-zinc-600">{r.stats?.scored ?? 0} scored</span>
                      </div>
                      <span className="text-zinc-500">{timeAgo(r.finished_at ?? r.started_at)}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-zinc-500 text-xs">No scans recorded yet.</p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <Suspense fallback={null}>
      <OverviewInner />
    </Suspense>
  );
}
