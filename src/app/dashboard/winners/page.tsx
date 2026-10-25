"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import useSWR from "swr";
import { CalendarDays, Download, Info, Lock, Trophy } from "lucide-react";
import Topbar from "@/components/layout/Topbar";
import MarketPicker from "@/components/winners/MarketPicker";
import WinnerCard, { LockedWinnerCard } from "@/components/winners/WinnerCard";
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

      <div className="p-4 md:p-6 space-y-5 max-w-6xl w-full mx-auto">
        {/* Header */}
        <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4">
          <div className="space-y-1">
            <h2 className="text-white text-xl font-semibold flex items-center gap-2">
              <Trophy size={18} className="text-amber-300" />
              {marketInfo ? `${marketInfo.flag} ${marketInfo.name}` : "Winning products"}
            </h2>
            <p className="text-zinc-500 text-sm">
              {data?.date
                ? `${nWinners} winner${nWinners === 1 ? "" : "s"}${nRising ? ` + ${nRising} rising` : ""} picked on ${new Date(data.date + "T00:00:00").toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" })}`
                : "Only products scoring 70+ make the list. Updated every day."}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {dates && dates.dates.length > 1 && (
              <label className="flex items-center gap-1.5 bg-zinc-900 border border-zinc-800 rounded-lg px-2.5 py-1.5 text-xs text-zinc-400">
                <CalendarDays size={13} />
                <select
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
              className="flex items-center gap-1.5 bg-zinc-900 border border-zinc-800 hover:border-zinc-700 rounded-lg px-3 py-1.5 text-xs text-zinc-300 disabled:opacity-40"
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
            <Trophy className="mx-auto text-zinc-600" />
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
            <p><b className="text-zinc-200">Scaling proof (30)</b> — ads running 14+ days, 5+ creatives, new creatives this week, reach / budget.</p>
            <p><b className="text-zinc-200">Engagement (25)</b> — TikTok engagement rate, shares, &quot;where can I buy&quot; comments, ad CTR.</p>
            <p><b className="text-zinc-200">Proven demand (20)</b> — 3–15 different stores selling it, many creators, total views.</p>
            <p><b className="text-zinc-200">Margin (15)</b> — sells for 3×+ the supplier cost, ideally $20–60.</p>
            <p><b className="text-zinc-200">Freshness (10)</b> — new, accelerating, and has a wow / problem-solving effect.</p>
            <p><b className="text-zinc-200">Removed</b> — restricted items, brand copies, saturated (50+ stores), already picked in the last 30 days.</p>
          </div>
        </details>
      </div>
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
