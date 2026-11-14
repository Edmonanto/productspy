"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import useSWR, { mutate, preload } from "swr";
import { AlertTriangle, CalendarDays, Download, Eye, Home, Info, LayoutGrid, List, Loader2, Lock, TrendingUp, Trophy } from "lucide-react";
import Topbar from "@/components/layout/Topbar";
import MarketPicker from "@/components/winners/MarketPicker";
import WinnerCard, { LockedWinnerCard } from "@/components/winners/WinnerCard";
import CompareTray from "@/components/research/CompareTray";
import { PickTile } from "@/components/visual/Visuals";
import { winnersApi } from "@/lib/api";
import { useMarket } from "@/lib/useMarket";

function WinnersInner() {
  const router = useRouter();
  const params = useSearchParams();
  const date = params.get("date") ?? undefined;
  const { market, setMarket, meta } = useMarket();
  const [exportError, setExportError] = useState<string | null>(null);
  // Grid (pictures) or list (details) — remembered per browser.
  const [view, setView] = useState<"grid" | "list">("grid");
  useEffect(() => { try { const v = localStorage.getItem("ps.view"); if (v === "list" || v === "grid") setView(v); } catch {} }, []);
  const pickView = (v: "grid" | "list") => { setView(v); try { localStorage.setItem("ps.view", v); } catch {} };

  // keepPreviousData: switching market keeps the current picks on screen
  // (dimmed) instead of flashing empty skeletons while the next list loads.
  const { data, error, isLoading, isValidating } = useSWR(
    market ? ["winners", market, date] : null,
    () => winnersApi.list(market!, date),
    { refreshInterval: 15 * 60_000, keepPreviousData: true }
  );
  const switching = isValidating && !!data && data.market !== undefined && data.market !== market;
  // Load the other followed markets in the background so switching is instant.
  const followingKey = (meta.data?.following ?? []).join(",");
  useEffect(() => {
    if (date) return;
    for (const code of followingKey.split(",")) {
      if (code && code !== market) preload(["winners", code, undefined], () => winnersApi.list(code));
    }
  }, [followingKey, market, date]);
  type Tier = "all" | "winner" | "rising" | "watch";
  const [tier, setTier] = useState<Tier>("all");
  useEffect(() => { setTier("all"); }, [market]);
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
  const shown = tier === "all" ? winners : winners.filter((w) => w.locked || w.tier === tier);

  // What to look at first: the top pick, the best margin, the most stores,
  // and any pick whose evidence is thin.
  const open = winners.filter((w) => !w.locked && w.product);
  const top = open[0];
  const marginOf = (w: (typeof open)[number]) => (w.economics?.complete ? w.economics.contribution_margin_pct : null);
  const bestMargin = open.filter((w) => marginOf(w) != null).sort((a, b) => (marginOf(b) ?? 0) - (marginOf(a) ?? 0))[0];
  const mostStores = open.filter((w) => w.stats?.stores).sort((a, b) => (b.stats?.stores ?? 0) - (a.stats?.stores ?? 0))[0];
  const thin = open.filter((w) => w.confidence === "low").length;

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
            <div className="flex bg-zinc-900 border border-zinc-800 rounded-lg p-0.5" role="group" aria-label="View">
              {([["grid", LayoutGrid, "Pictures"], ["list", List, "Details"]] as const).map(([v, Icon, label]) => (
                <button key={v} onClick={() => pickView(v)} aria-pressed={view === v} title={label}
                        className={`flex items-center gap-1 rounded-md px-3 py-1.5 max-md:min-h-[40px] text-xs font-medium transition-all duration-150 active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400 ${view === v ? "bg-violet-600 text-white shadow" : "text-zinc-400 hover:text-white hover:bg-zinc-800"}`}>
                  <Icon size={14} /> <span className="hidden sm:inline">{label}</span>
                </button>
              ))}
            </div>
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
              className="flex items-center gap-1.5 bg-zinc-900 border border-zinc-800 hover:border-zinc-600 hover:text-white rounded-lg px-3 py-1.5 max-md:min-h-[44px] text-xs text-zinc-300 transition-all duration-150 active:scale-95 disabled:opacity-40"
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
              <button
                onClick={async () => {
                  const max = meta.data?.entitlements.markets ?? 1;
                  const cur = meta.data?.following ?? [];
                  const next = cur.length < max ? [...cur, market!] : [...cur.slice(0, max - 1), market!];
                  await winnersApi.setMarkets(next);
                  await mutate("winner-markets");
                  await mutate(["winners", market, date]);
                }}
                className="px-4 py-2 rounded-lg bg-zinc-800 text-zinc-200 text-sm hover:bg-zinc-700"
              >
                Switch to this market
              </button>
              <Link href="/dashboard/billing" className="px-4 py-2 rounded-lg bg-violet-600 text-white text-sm hover:bg-violet-500">
                Upgrade
              </Link>
            </div>
          </div>
        ) : err ? (
          <div className="bg-red-500/10 border border-red-500/20 text-red-300 rounded-xl p-4 text-sm">{err.message}</div>
        ) : (isLoading && !data) || !market ? (
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
          <div className={`space-y-3 transition-opacity duration-150 ${switching ? "opacity-50 pointer-events-none" : ""}`} aria-busy={switching}>
            {switching && (
              <div className="flex items-center gap-2 text-xs text-violet-200">
                <Loader2 size={13} className="animate-spin" /> Loading {marketInfo?.name ?? market}…
              </div>
            )}

            {/* Pay attention: the few numbers that matter most today */}
            {top?.product && (
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
                <Link href={`/dashboard/winners/${top.product.id}?market=${market}`}
                      className="rounded-xl border border-amber-400/40 bg-amber-400/10 px-3 py-2.5 hover:border-amber-300 transition-colors active:scale-[.98]">
                  <div className="text-[11px] uppercase tracking-wide text-amber-300 font-semibold flex items-center gap-1"><Trophy size={12} /> Top pick</div>
                  <div className="text-sm text-white font-semibold line-clamp-1">{top.product.title}</div>
                  <div className="text-xs text-amber-200 tabular-nums">Score <b className="text-amber-100">{top.total}</b>/100</div>
                </Link>
                {bestMargin?.product ? (
                  <Link href={`/dashboard/winners/${bestMargin.product.id}?market=${market}`}
                        className="rounded-xl border border-emerald-400/40 bg-emerald-400/10 px-3 py-2.5 hover:border-emerald-300 transition-colors active:scale-[.98]">
                    <div className="text-[11px] uppercase tracking-wide text-emerald-300 font-semibold flex items-center gap-1"><TrendingUp size={12} /> Best margin</div>
                    <div className="text-sm text-white font-semibold line-clamp-1">{bestMargin.product.title}</div>
                    <div className="text-xs text-emerald-200 tabular-nums"><b className="text-emerald-100">{Math.round(marginOf(bestMargin) ?? 0)}%</b> before ads</div>
                  </Link>
                ) : <div className="hidden lg:block" />}
                {mostStores?.product ? (
                  <Link href={`/dashboard/winners/${mostStores.product.id}?market=${market}`}
                        className="rounded-xl border border-sky-400/40 bg-sky-400/10 px-3 py-2.5 hover:border-sky-300 transition-colors active:scale-[.98]">
                    <div className="text-[11px] uppercase tracking-wide text-sky-300 font-semibold flex items-center gap-1"><Home size={12} /> Most stores</div>
                    <div className="text-sm text-white font-semibold line-clamp-1">{mostStores.product.title}</div>
                    <div className="text-xs text-sky-200 tabular-nums"><b className="text-sky-100">{mostStores.stats?.stores}</b> stores advertising it</div>
                  </Link>
                ) : <div className="hidden lg:block" />}
                <div className={`rounded-xl border px-3 py-2.5 ${thin ? "border-orange-400/40 bg-orange-400/10" : "border-zinc-800 bg-zinc-900"}`}>
                  <div className={`text-[11px] uppercase tracking-wide font-semibold flex items-center gap-1 ${thin ? "text-orange-300" : "text-zinc-400"}`}>
                    <AlertTriangle size={12} /> Check before you buy
                  </div>
                  <div className="text-xs text-zinc-300 mt-0.5">
                    {thin
                      ? <><b className="text-orange-200">{thin}</b> pick{thin === 1 ? " has" : "s have"} thin evidence (low confidence) — open them and check the ads first.</>
                      : "Every pick has medium or high confidence."}
                  </div>
                </div>
              </div>
            )}

            {/* Tier filter */}
            <div className="flex items-center gap-1.5 flex-wrap" role="tablist" aria-label="Filter picks">
              {([
                ["all", "All", winners.length, "bg-violet-600 text-white border-violet-400"],
                ["winner", "Winners", nWinners, "bg-emerald-500 text-emerald-950 border-emerald-300"],
                ["rising", "Rising", nRising, "bg-amber-400 text-amber-950 border-amber-200"],
                ["watch", "To watch", nWatch, "bg-sky-500 text-sky-950 border-sky-300"],
              ] as const).filter(([t, , n]) => t === "all" || n > 0).map(([t, label, n, on]) => (
                <button key={t} role="tab" aria-selected={tier === t} onClick={() => setTier(t)}
                        className={`flex items-center gap-1.5 rounded-full border px-3.5 py-1.5 max-md:min-h-[40px] text-xs font-semibold select-none transition-all duration-150 active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400 ${tier === t ? on : "bg-zinc-900 text-zinc-300 border-zinc-700 hover:text-white hover:border-zinc-500"}`}>
                  {t === "watch" ? <Eye size={12} /> : t === "winner" ? <Trophy size={12} /> : null}
                  {label}
                  <span className={`rounded-full px-1.5 tabular-nums ${tier === t ? "bg-black/20" : "bg-zinc-800 text-zinc-400"}`}>{n}</span>
                </button>
              ))}
            </div>

            {nWatch > 0 && nWinners + nRising === 0 && (
              <div className="text-xs text-sky-200 bg-sky-500/10 border border-sky-500/20 rounded-lg px-3 py-2">
                No product reached 55 in this scan, so these are the strongest early signals (40–54) — worth watching,
                not yet proven. Scores rise as the same product shows up across more stores and platforms.
              </div>
            )}
            {view === "grid" ? (
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
                {shown.map((w) =>
                  w.locked ? <div key={w.rank} className="col-span-full"><LockedWinnerCard pick={w} /></div>
                    : <PickTile key={w.rank} pick={w} market={market} />
                )}
              </div>
            ) : shown.map((w) =>
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
