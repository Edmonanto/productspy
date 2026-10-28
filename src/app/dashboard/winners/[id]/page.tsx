"use client";

import { Suspense, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import useSWR from "swr";
import {
  ArrowLeft, Bookmark, CheckCircle2, Columns3, Download, ImageOff, Lock, Package, PlayCircle, Sparkles,
} from "lucide-react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import Topbar from "@/components/layout/Topbar";
import ScoreRing from "@/components/winners/ScoreRing";
import ProductImage from "@/components/products/ProductImage";
import { CriteriaRadar, ProductVisual } from "@/components/visual/Visuals";
import ProfitCalculator from "@/components/products/ProfitCalculator";
import QuoteForm from "@/components/products/QuoteForm";
import { Empty, Section } from "@/components/research/Section";
import CriteriaBreakdown from "@/components/research/CriteriaBreakdown";
import TrendPanel, { TrendBadge } from "@/components/research/TrendPanel";
import AIReportPanel, { ReportCTA } from "@/components/research/AIReportPanel";
import ValidationPanel from "@/components/research/ValidationPanel";
import {
  CompetitorSection, CreativeSection, MarketSection, RisksSection, SupplierSection,
} from "@/components/research/ReportSections";
import { AdAngle, AdEvidence, researchApi, watchlistApi, winnersApi } from "@/lib/api";
import { useCompare } from "@/lib/compare";
import { cn, fmtNum, fmtPct, formatPrice, recallMarket, scoreBand, SOURCE_LABEL, timeAgo } from "@/lib/utils";
import { computeEconomics, DEFAULT_ASSUMPTIONS } from "@/lib/profit";

const TABS = [
  { key: "meta", label: "Facebook / Instagram ads" },
  { key: "tiktok_ads", label: "TikTok ads" },
  { key: "tiktok_organic", label: "TikTok videos" },
];

const NAV = [
  ["overview", "Overview"], ["score", "Score"], ["demand", "Demand"], ["evidence", "Evidence"],
  ["competitors", "Competitors"], ["profit", "Profit"], ["market", "Market"], ["creative", "Creative"],
  ["supplier", "Supplier"], ["risks", "Risks"], ["validation", "Validation"], ["ai", "AI recommendation"],
] as const;

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
    <div className="bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden flex flex-col break-inside-avoid">
      <div className="aspect-video bg-zinc-800 relative">
        <ProductImage src={ad.thumbnail_url} alt={ad.advertiser_name ?? "Ad"} className="w-full h-full object-cover"
          fallback={<div className="w-full h-full flex items-center justify-center text-zinc-500"><ImageOff size={20} /></div>} />
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
        {ad.ad_text && <p className="text-zinc-400 line-clamp-2">{ad.ad_text}</p>}
        <div className="flex flex-wrap gap-1">
          {metrics.map((m) => <span key={m} className="bg-zinc-800 text-zinc-300 rounded px-1.5 py-0.5">{m}</span>)}
        </div>
      </div>
      <div className="flex border-t border-zinc-800 text-xs print:hidden">
        {ad.ad_url && <a href={ad.ad_url} target="_blank" rel="noreferrer" className="flex-1 text-center py-2 max-md:py-3 text-zinc-400 hover:text-white hover:bg-zinc-800">View</a>}
        {ad.landing_url && <a href={ad.landing_url} target="_blank" rel="noreferrer" className="flex-1 text-center py-2 max-md:py-3 text-zinc-400 hover:text-white hover:bg-zinc-800 border-l border-zinc-800">Store</a>}
      </div>
    </div>
  );
}

function Timeline({ ads }: { ads: AdEvidence[] }) {
  const dated = ads.filter((a) => a.started_at).sort((a, b) => (b.started_at! > a.started_at! ? 1 : -1)).slice(0, 12);
  if (!dated.length) return <Empty>No dated ads or videos yet.</Empty>;
  return (
    <ol className="relative border-l border-zinc-800 ml-1.5 space-y-3">
      {dated.map((a, i) => (
        <li key={`${a.ad_url}-${i}`} className="pl-4 relative">
          <span className="absolute -left-[5px] top-1.5 w-2.5 h-2.5 rounded-full bg-violet-500" aria-hidden />
          <div className="text-xs text-zinc-500">
            {new Date(a.started_at!).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })}
            {" · "}{a.platform === "tiktok_organic" ? "video posted" : "ad started"}
          </div>
          <div className="text-sm text-zinc-300">
            {SOURCE_LABEL[a.platform] ?? a.platform} — {a.advertiser_name ?? a.landing_domain ?? "unknown"}
            {a.days_running != null && a.platform !== "tiktok_organic" && <span className="text-zinc-500"> · still running after {a.days_running} days</span>}
            {a.views ? <span className="text-zinc-500"> · {fmtNum(a.views)} lifetime views</span> : null}
          </div>
        </li>
      ))}
    </ol>
  );
}

function EvidenceInner() {
  const { id } = useParams<{ id: string }>();
  const params = useSearchParams();
  const market = (params.get("market") ?? recallMarket() ?? "US").toUpperCase();
  const [tab, setTab] = useState("meta");
  const [quoteQty, setQuoteQty] = useState<number | null>(null);
  const [genBusy, setGenBusy] = useState(false);
  const [genError, setGenError] = useState<string | null>(null);
  const compare = useCompare();

  const { data, error, isLoading } = useSWR(["evidence", id, market], () => winnersApi.product(id, market));
  const { data: rep, mutate: mutateReport } = useSWR(["report", id, market], () => researchApi.report(id, market), {
    refreshInterval: (d) => (d?.report?.status === "pending" ? 3000 : 0),
  });
  const { data: markets } = useSWR("winner-markets", winnersApi.markets);
  const { data: watch, mutate: mutateWatch } = useSWR("watchlist", watchlistApi.list);
  const saved = !!watch?.items.some((w) => w.product.id === id);

  const ads = useMemo(() => Object.values(data?.ads ?? {}).flat().filter(Boolean), [data]);

  if (error) return <div className="p-6 text-red-300 text-sm">{(error as Error).message}</div>;
  if (isLoading || !data) {
    return (
      <div className="p-6 space-y-4 animate-pulse max-w-6xl mx-auto w-full">
        <div className="h-8 w-64 bg-zinc-800 rounded" />
        <div className="h-64 bg-zinc-900 rounded-xl" />
        <div className="h-40 bg-zinc-900 rounded-xl" />
      </div>
    );
  }

  const { product: p, score } = data;
  const report = rep?.report ?? null;
  const ready = report?.status === "ready" ? report.report ?? undefined : undefined;
  const criteria = score?.criteria ?? {};
  const mk = markets?.markets.find((m) => m.code === market);
  const econ = computeEconomics({ price: p.price_usd, productCost: p.cost_usd, cpa: null, ...DEFAULT_ASSUMPTIONS });
  const firstTabWithAds = TABS.find((t) => (data.ads?.[t.key] ?? []).length)?.key;
  const activeTab = (data.ads?.[tab] ?? []).length ? tab : firstTabWithAds ?? tab;

  const generate = async (refresh = false) => {
    setGenBusy(true); setGenError(null);
    try {
      await researchApi.generate(id, market, refresh);
      await mutateReport();
    } catch (e) {
      setGenError((e as Error).message);
    } finally {
      setGenBusy(false);
    }
  };
  const toggleSave = async () => {
    try {
      if (saved) await watchlistApi.remove(id); else await watchlistApi.add(id);
      mutateWatch();
    } catch (e) {
      setGenError((e as Error).message);
    }
  };
  const reportProps = { report, quota: rep?.quota, busy: genBusy, error: genError, onGenerate: generate };

  return (
    <div className="p-4 md:p-6 max-w-6xl mx-auto w-full space-y-4">
      <div className="flex items-center justify-between gap-2 flex-wrap print:hidden">
        <Link href={`/dashboard/winners?market=${market}`} className="py-3 -my-3 inline-flex items-center gap-1 text-xs text-zinc-400 hover:text-white">
          <ArrowLeft size={12} /> Back to winners
        </Link>
        <div className="flex items-center gap-1.5 flex-wrap">
          <button onClick={toggleSave} className={cn("flex items-center gap-1.5 text-xs rounded-lg px-3 py-2 min-h-[40px] border",
            saved ? "text-violet-300 border-violet-500/40 bg-violet-500/10" : "text-zinc-300 border-zinc-800 bg-zinc-900 hover:border-zinc-700")}>
            <Bookmark size={13} fill={saved ? "currentColor" : "none"} /> {saved ? "Saved" : "Save"}
          </button>
          <button onClick={() => compare.toggle(id)} className={cn("flex items-center gap-1.5 text-xs rounded-lg px-3 py-2 min-h-[40px] border",
            compare.has(id) ? "text-violet-300 border-violet-500/40 bg-violet-500/10" : "text-zinc-300 border-zinc-800 bg-zinc-900 hover:border-zinc-700")}>
            <Columns3 size={13} /> {compare.has(id) ? "In comparison" : "Compare"}
          </button>
          <button onClick={() => window.print()} className="flex items-center gap-1.5 text-xs text-zinc-300 border border-zinc-800 bg-zinc-900 hover:border-zinc-700 rounded-lg px-3 py-2 min-h-[40px]">
            <Download size={13} /> Export report (PDF)
          </button>
        </div>
      </div>

      {/* Section nav */}
      <nav aria-label="Report sections" className="sticky top-14 z-20 -mx-4 md:-mx-6 px-4 md:px-6 bg-zinc-950/95 backdrop-blur border-b border-zinc-800 print:hidden">
        <div className="flex gap-1 overflow-x-auto py-2">
          {NAV.map(([key, label]) => (
            <a key={key} href={`#${key}`} className="text-xs text-zinc-400 hover:text-white bg-zinc-900 border border-zinc-800 rounded-full px-3 py-1.5 whitespace-nowrap">
              {label}
            </a>
          ))}
        </div>
      </nav>

      {/* 1 Overview */}
      <Section id="overview" n={1} title="Product overview">
        <div className="grid md:grid-cols-[180px_1fr] lg:grid-cols-[200px_1fr_250px] gap-5">
          <ProductVisual src={p.image_url} alt={p.title} category={p.category} iconSize={48}
                         className="h-48 sm:h-60 md:h-auto md:aspect-square rounded-lg" />
          <div className="space-y-3 min-w-0">
            <div>
              <h2 className="text-white text-xl font-semibold leading-snug">{p.title}</h2>
              <div className="text-xs text-zinc-400 mt-1 flex flex-wrap gap-x-2 gap-y-1 items-center">
                {p.category && <span className="capitalize">{p.category.replace("-", " ")}</span>}
                <span>· {mk ? `${mk.flag} ${mk.name}` : market}</span>
                {p.first_seen_at && <span>· first seen {new Date(p.first_seen_at).toLocaleDateString()}</span>}
                {score && <span>· research updated {timeAgo(score.scored_on + "T12:00:00Z")}</span>}
              </div>
            </div>
            {ready && <p className="text-sm text-zinc-300">{ready.ai.description} <span className="text-zinc-500">Solves: {ready.ai.primary_problem}</span></p>}
            {score?.strengths?.length ? (
              <ul className="space-y-1.5">
                {score.strengths.slice(0, 3).map((r) => (
                  <li key={r} className="flex gap-2 text-sm text-zinc-300"><CheckCircle2 size={15} className="text-emerald-400 mt-0.5 shrink-0" /> {r}</li>
                ))}
              </ul>
            ) : null}
            <div className="grid grid-cols-3 gap-2 max-w-md">
              <div className="bg-zinc-800/60 rounded-lg px-3 py-2">
                <div className="text-[11px] text-zinc-500">Competitor price</div>
                <div className="text-white font-semibold text-sm">{formatPrice(p.price_usd)}</div>
              </div>
              <div className="bg-zinc-800/60 rounded-lg px-3 py-2">
                <div className="text-[11px] text-zinc-500">Product cost{p.cost_estimated && " (AI est.)"}</div>
                <div className="text-white font-semibold text-sm">{formatPrice(p.cost_usd)}</div>
              </div>
              <div className="bg-zinc-800/60 rounded-lg px-3 py-2">
                <div className="text-[11px] text-zinc-500">Margin before ads</div>
                <div className={cn("font-semibold text-sm", econ.contributionMarginPct == null ? "text-zinc-400" : econ.contributionMarginPct >= 30 ? "text-emerald-400" : "text-amber-300")}>
                  {econ.contributionMarginPct == null ? "Incomplete" : `${econ.contributionMarginPct}%`}
                </div>
              </div>
            </div>
          </div>
          <div className="space-y-3 md:col-span-2 lg:col-span-1 lg:border-l lg:border-zinc-800 lg:pl-5">
            {score ? (
              <>
                <div className="flex items-center gap-3">
                  <ScoreRing score={score.total} size={84} stroke={7} />
                  <div className="text-xs space-y-1">
                    <div className="text-zinc-200 font-medium leading-snug">{score.band ?? scoreBand(score.total)}</div>
                    <div className="capitalize text-zinc-400">{score.confidence} confidence</div>
                    <TrendBadge trend={score.trend} />
                  </div>
                </div>
                <CriteriaRadar breakdown={score.breakdown} size={200} compact />
              </>
            ) : <Empty>Not scored in this market yet.</Empty>}
            {!ready && <div className="print:hidden"><ReportCTA {...reportProps} /></div>}
          </div>
        </div>
      </Section>

      {/* 2 Score */}
      <Section id="score" n={2} title="Winning Product Score breakdown"
               subtitle="Eight criteria. Criteria without data are left out and the rest scaled — never counted as zero.">
        {score ? (
          <>
            <CriteriaBreakdown criteria={criteria} comments={ready?.ai.criteria_comments} />
            <div className="grid md:grid-cols-[1fr_280px] gap-4 items-start">
              <p className="text-xs text-zinc-500 leading-relaxed">
                {score.known_points != null && <>Evidence covers {Math.round(score.known_points)} of 100 weighted points. </>}
                Confidence is high when the product is seen on two or more platforms with most criteria known; a
                “winner” needs medium or high confidence. Tags show where each point comes from: observed in ads,
                calculated by ProductSpy, AI-assessed, or an assumption you can change in the calculator.
              </p>
              {(data.history ?? []).length > 1 && (
                <div>
                  <div className="text-[11px] text-zinc-500 mb-1">Score over time</div>
                  <div className="h-24">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={data.history} margin={{ left: -28, right: 4, top: 4, bottom: 0 }}>
                        <XAxis dataKey="date" hide />
                        <YAxis domain={[0, 100]} tick={{ fill: "#a1a1aa", fontSize: 10 }} tickLine={false} axisLine={false} />
                        <Tooltip contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", fontSize: 12 }} />
                        <Line type="monotone" dataKey="total" name="Score" stroke="#a78bfa" strokeWidth={2} dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}
            </div>
          </>
        ) : <Empty>No score yet.</Empty>}
      </Section>

      {/* 3 Demand */}
      <Section id="demand" n={3} title="Demand & trend analysis">
        {score ? (
          <>
            <TrendPanel trend={score.trend ?? "unknown"} why={score.trend_why ?? null} signals={score.signals ?? {}} history={data.history ?? []} search={data.search_trend ?? null} />
            {ready && <p className="text-sm text-zinc-300 border-t border-zinc-800 pt-3"><span className="text-violet-300 text-xs mr-1">AI summary</span>{ready.ai.demand_summary}</p>}
          </>
        ) : <Empty>No demand data yet.</Empty>}
      </Section>

      {/* 4 Evidence */}
      <Section id="evidence" n={4} title="Source evidence & timeline"
               subtitle="The ads and videos behind the score. Views are lifetime counts — interest, not sales.">
        {data.ad_evidence_locked ? (
          <div className="text-center py-8 space-y-2">
            <Lock className="mx-auto text-violet-300" />
            <p className="text-zinc-300 text-sm">{Object.values(data.ad_counts ?? {}).reduce((a, b) => a + b, 0)} ads & videos found for this product.</p>
            <Link href="/dashboard/billing" className="inline-block px-4 py-2 rounded-lg bg-violet-600 text-white text-sm hover:bg-violet-500">Upgrade to see them</Link>
          </div>
        ) : (
          <div className="grid lg:grid-cols-[1fr_300px] gap-5">
            <div className="space-y-3 min-w-0">
              <div className="flex gap-1 overflow-x-auto -mx-1 px-1 print:hidden" role="tablist">
                {TABS.filter((t) => t.key === activeTab || (data.ad_counts?.[t.key] ?? 0) > 0).map((t) => (
                  <button key={t.key} role="tab" aria-selected={activeTab === t.key} onClick={() => setTab(t.key)}
                          className={cn("px-3 py-2 md:py-1.5 max-md:min-h-[44px] rounded-lg text-xs whitespace-nowrap shrink-0",
                            activeTab === t.key ? "bg-zinc-800 text-white" : "text-zinc-400 hover:text-white")}>
                    {t.label} <span className="text-zinc-500">{data.ad_counts?.[t.key] ?? 0}</span>
                  </button>
                ))}
              </div>
              {(data.ads?.[activeTab] ?? []).length === 0 ? (
                <Empty>Nothing from {SOURCE_LABEL[activeTab]} for this product yet.</Empty>
              ) : (
                <div className="grid grid-cols-1 min-[420px]:grid-cols-2 xl:grid-cols-3 gap-3">
                  {(data.ads?.[activeTab] ?? []).map((ad, i) => <AdCard key={`${ad.ad_url}-${i}`} ad={ad} />)}
                </div>
              )}
            </div>
            <div>
              <h4 className="text-xs font-semibold text-zinc-300 mb-3">Timeline</h4>
              <Timeline ads={ads} />
            </div>
          </div>
        )}
      </Section>

      {/* 5 Competitors */}
      <Section id="competitors" n={5} title="Competitor comparison">
        <CompetitorSection report={ready} ads={ads} criteria={criteria} />
      </Section>

      {/* 6 Profit */}
      <ProfitCalculator key={p.id} n={6} priceUsd={p.price_usd} costUsd={p.cost_usd} costEstimated={p.cost_estimated} onRequestQuote={setQuoteQty} />
      <QuoteForm productId={p.id} productTitle={p.title} initialQuantity={quoteQty ?? 100} open={quoteQty != null} onClose={() => setQuoteQty(null)} />

      {/* 7 Market */}
      <Section id="market" n={7} title="Target market analysis">
        <MarketSection report={ready} criteria={criteria} market={{ name: mk?.name ?? market, currency: mk?.currency ?? "USD", flag: mk?.flag }} />
      </Section>

      {/* 8 Creative */}
      <Section id="creative" n={8} title="Advertising & creative opportunities">
        <CreativeSection report={ready} criteria={criteria} suggested={p.angles ?? (p.attributes?.angles as AdAngle[] | undefined) ?? []} />
      </Section>

      {/* 9 Supplier */}
      <Section id="supplier" n={9} title="Supplier & fulfilment">
        <SupplierSection suppliers={data.suppliers ?? []} criteria={criteria} costUsd={p.cost_usd} costEstimated={p.cost_estimated}
                         onQuote={() => setQuoteQty(100)} report={ready} />
      </Section>

      {/* 10 Risks */}
      <Section id="risks" n={10} title="Risks & missing information">
        <RisksSection weaknesses={score?.weaknesses ?? []} missing={score?.missing ?? []} report={ready} criteria={criteria} excluded={score?.excluded ?? null} />
      </Section>

      {/* 11 Validation */}
      <Section id="validation" n={11} title="Validation checklist">
        <ValidationPanel productId={p.id} />
      </Section>

      {/* 12 AI */}
      <Section id="ai" n={12} title="AI recommendation"
               actions={<Sparkles size={16} className="text-violet-400" aria-hidden />}>
        <AIReportPanel {...reportProps} />
      </Section>

      <p className="text-[11px] text-zinc-500 text-center pb-4">
        ProductSpy Pro research for {p.title} · {mk?.name ?? market} · {score ? `scored ${score.scored_on}` : "not scored"} ·
        assumptions: ${DEFAULT_ASSUMPTIONS.shipping} shipping, {DEFAULT_ASSUMPTIONS.feePct}% + ${DEFAULT_ASSUMPTIONS.feeFixed} fees, {DEFAULT_ASSUMPTIONS.returnsPct}% returns.
      </p>
    </div>
  );
}

export default function EvidencePage() {
  return (
    <div className="flex flex-col min-h-full">
      <div className="print:hidden"><Topbar title="Product research" /></div>
      <Suspense fallback={null}>
        <EvidenceInner />
      </Suspense>
    </div>
  );
}
