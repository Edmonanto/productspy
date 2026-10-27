"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import useSWR from "swr";
import { CalendarDays, Download, Info, Lock, Trophy } from "lucide-react";
import Topbar from "@/components/layout/Topbar";
import MarketPicker from "@/components/winners/MarketPicker";
import WinnerCard, { LockedWinnerCard } from "@/components/winners/WinnerCard";
import CompareTray from "@/components/research/CompareTray";
import { winnersApi } from "@/lib/api";
import { useMarket } from "@/lib/useMarket";

function WinnersInner() {
  const router = useRouter();
  const params = useSearchParams();
  const date = params.get("date") ?? undefined;
  const { market, setMarket, meta } = useMarket();
  const [exportError, setExportError] = useState<string | null>(null);

  const { data, error, isLoading } = useSWR(
    market ? ["winners", market, date] : null,
    () => winnersApi.list(market!, date),
    { refreshInterval: 15 * 60_000 }
  );
  const { data: dates } = useSWR(market ? ["winner-dates", market] : null, () => winnersApi.dates(market!));
  const { data: runs } = useSWR("winner-status", winnersApi.status);
  const lastRun = runs?.runs.find((r) => r.market === market);

  const ent = meta.data?.entitlements;
  const err = error as (Error & { code?: string }) | undefined;
  const winners = data?.winners ?? [];
  const nWinners = winners.filter((w) => w.tier === "winner").length;
  const nRising = winners.filter((w) => w.tier === "rising").length;
  const nWatch = winners.filter((w) => w.tier === "watch").length;
  const marketInfo = meta.data?.markets.find((m) => m.code === market);

  const pickDate = (d: string) => {
    const q = new URLSearchParams(params.toString());
    if (d) q.set("date", d);
    else q.delete("date");
    router.replace(`/dashboard/winners?${q.toString()}`);
  };

  const doExport = async () => {
    setExportError(null);
    try {
      await winnersApi.exportCsv(market!, data?.date ?? undefined);
    } catch (e) {
      setExportError((e as Error).message);
    }
  };

  return (
    <div className="flex flex-col min-h-full">
      <Topbar title="Daily Winners" />

      <div className="p-4 md:p-6 pb-24 space-y-5 max-w-6xl w-full mx-auto">
        {/* Header */}
        <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4">
          <div className="space-y-1">
            <h2 className="text-white text-xl font-semibold flex items-center gap-2">
              <Trophy size={18} className="text-amber-300" />
              {marketInfo ? `${marketInfo.flag} ${marketInfo.name}` : "Winning products"}
            </h2>
            <p className="text-zinc-500 text-sm">
              {data?.date
                ? `${nWinners} winner${nWinners === 1 ? "" : "s"}${nRising ? ` + ${nRising} rising` : ""}${nWatch ? ` + ${nWatch} to watch` : ""} picked on ${new Date(data.date + "T00:00:00").toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" })}`
                : "Products are scored 0–100 on eight criteria, with the evidence for each. Updated every day."}
            </p>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {dates && dates.dates.length > 1 && (
              <label className="flex items-center gap-1.5 bg-zinc-900 border border-zinc-800 rounded-lg px-2.5 py-1.5 max-md:py-0 text-xs text-zinc-400">
                <CalendarDays size={13} />
                <select
                  aria-label="Pick a day"
                  value={date ?? ""}
                  onChange={(e) => pickDate(e.target.value)}
                  className="bg-transparent text-zinc-200 focus:outline-none"
                >
                  <option value="">Latest</option>
                  {dates.dates.map((d) => (
                    <option key={d.date} value={d.date}>{d.date} · {d.winners} winners</option>
                  ))}
                </select>
              </label>
            )}
            <button
              onClick={doExport}
              disabled={!data?.date}
              className="flex items-center gap-1.5 bg-zinc-900 border border-zinc-800 hover:border-zinc-700 rounded-lg px-3 py-1.5 max-md:min-h-[44px] text-xs text-zinc-300 disabled:opacity-40"
            >
              {ent?.export_csv ? <Download size={13} /> : <Lock size={13} />}
              Export CSV
            </button>
          </div>
        </div>

        {meta.data && market && (
          <MarketPicker
            markets={meta.data.markets}
            following={meta.data.following.includes(market) ? meta.data.following : [...meta.data.following, market]}
            value={market}
            onChange={setMarket}
          />
        )}

        {exportError && (
          <div className="text-xs text-amber-300 bg-amber-500/10 border border-amber-500/20 rounded-lg px-3 py-2">
            {exportError} — <Link href="/dashboard/billing" className="underline">see plans</Link>
          </div>
        )}

        {/* States */}
        {err?.code === "market_locked" ? (
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-8 text-center space-y-3">
            <Lock className="mx-auto text-violet-300" />
            <p className="text-white font-medium">This market isn&apos;t on your plan</p>
            <p className="text-zinc-500 text-sm max-w-md mx-auto">{err.message}</p>
            <div className="flex justify-center gap-2">
              <Link href="/dashboard/settings" className="px-4 py-2 rounded-lg bg-zinc-800 text-zinc-200 text-sm hover:bg-zinc-700">
                Change market
              </Link>
              <Link href="/dashboard/billing" className="px-4 py-2 rounded-lg bg-violet-600 text-white text-sm hover:bg-violet-500">
                Upgrade
              </Link>
            </div>
          </div>
        ) : err ? (
          <div className="bg-red-500/10 border border-red-500/20 text-red-300 rounded-xl p-4 text-sm">{err.message}</div>
        ) : isLoading || !market ? (
          <div className="space-y-3">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="h-44 bg-zinc-900 border border-zinc-800 rounded-xl animate-pulse" />
            ))}
          </div>
        ) : winners.length === 0 ? (
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-10 text-center space-y-2">
            <Trophy className="mx-auto text-zinc-500" />
            <p className="text-white font-medium">No picks yet for this market</p>
            <p className="text-zinc-500 text-sm">
              {lastRun
                ? `Last scan ${new Date(lastRun.finished_at ?? lastRun.started_at).toLocaleString()} · ${lastRun.stats?.scored ?? 0} products scored`
                : data?.message ?? "The daily scan runs every morning. Check back soon."}
            </p>
            {lastRun?.problem && (
              <p className="text-amber-300 text-xs max-w-lg mx-auto bg-amber-500/10 border border-amber-500/20 rounded-lg px-3 py-2">
                {lastRun.problem}
              </p>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            {nWatch > 0 && nWinners + nRising === 0 && (
              <div className="text-xs text-sky-200 bg-sky-500/10 border border-sky-500/20 rounded-lg px-3 py-2">
                No product reached 55 in this scan, so these are the strongest early signals (40–54) — worth watching,
                not yet proven. Scores rise as the same product shows up across more stores and platforms.
              </div>
            )}
            {winners.map((w) =>
              w.locked ? <LockedWinnerCard key={w.rank} pick={w} /> : <WinnerCard key={w.rank} pick={w} market={market} />
            )}
          </div>
        )}

        {/* How we pick */}
        <details className="bg-zinc-900/60 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-zinc-400">
          <summary className="cursor-pointer text-zinc-300 flex items-center gap-2">
            <Info size={14} /> How products are scored
          </summary>
          <div className="mt-3 grid md:grid-cols-2 gap-x-8 gap-y-1.5 text-xs leading-relaxed">
            <p><b className="text-zinc-200">Demand & trend (20)</b> — stores advertising it, how long ads keep running, new ads in the last 14 days, creators, recent video velocity.</p>
            <p><b className="text-zinc-200">Profitability (20)</b> — contribution margin after cost, shipping, fees and returns; price band; markup.</p>
            <p><b className="text-zinc-200">Competition (15)</b> — 3–15 stores is validated but open; 1 is unproven; 30+ is crowded.</p>
            <p><b className="text-zinc-200">Creative potential (10)</b> — scroll-stopping, problem-solving, shown in 3 seconds; observed engagement.</p>
            <p><b className="text-zinc-200">Differentiation (10)</b> — bundle/upsell and branding potential (AI-assessed).</p>
            <p><b className="text-zinc-200">Logistics (10)</b> — fragile/heavy, shipping cost relative to price.</p>
            <p><b className="text-zinc-200">Market fit (10)</b> — advertised to shoppers in this market, local price found.</p>
            <p><b className="text-zinc-200">Risk (5)</b> — brand look-alike, seasonality, declining ads.</p>
            <p className="md:col-span-2"><b className="text-zinc-200">Honest scoring</b> — criteria without data are left out, not counted as zero; single-platform products are capped at 85; a “winner” (70+) needs medium or high confidence. 55–69 is promising, 40–54 is an early signal. Restricted items, brand copies and products picked in the last 30 days are removed. Scores support your decision — they don&apos;t guarantee sales.</p>
          </div>
        </details>
      </div>
      <CompareTray market={market} />
    </div>
  );
}

export default function WinnersPage() {
  return (
    <Suspense fallback={null}>
      <WinnersInner />
    </Suspense>
  );
}
