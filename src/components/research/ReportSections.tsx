/** Sections 5, 7, 8, 9, 10 of the product report. Each shows what the data supports and says what's missing. */
import { AlertTriangle, ExternalLink, Package } from "lucide-react";
import { AdEvidence, Criterion, ResearchReport } from "@/lib/api";
import { cn, CriterionKey, formatPrice, SOURCE_LABEL } from "@/lib/utils";
import CriteriaBreakdown from "./CriteriaBreakdown";
import { Bullets, Empty, KindTag } from "./Section";

type Criteria = Partial<Record<CriterionKey, Criterion>>;
type Report = ResearchReport["report"];

const CUES: Record<string, string> = {
  free_shipping: "Free shipping", money_back: "Money-back guarantee", returns_30d: "30-day returns", bundle_offer: "Bundle / multi-buy",
};

function StoresFromAds({ ads }: { ads: AdEvidence[] }) {
  const stores = new Map<string, AdEvidence>();
  ads.forEach((a) => { const d = a.landing_domain; if (d && !stores.has(d)) stores.set(d, a); });
  if (!stores.size) return <Empty>No competitor store links in the ads we collected.</Empty>;
  return (
    <ul className="divide-y divide-zinc-800">
      {Array.from(stores.entries()).slice(0, 10).map(([d, a]) => (
        <li key={d} className="flex items-center justify-between gap-2 py-2 text-sm">
          <span className="text-zinc-300 truncate">{d}</span>
          <span className="flex items-center gap-3 text-xs text-zinc-500 shrink-0">
            {SOURCE_LABEL[a.platform] ?? a.platform}
            {a.landing_url && <a href={a.landing_url} target="_blank" rel="noreferrer" className="text-violet-300 hover:underline flex items-center gap-1">Store <ExternalLink size={11} /></a>}
          </span>
        </li>
      ))}
    </ul>
  );
}

export function CompetitorSection({ report, ads, criteria }: { report: Report | undefined; ads: AdEvidence[]; criteria: Criteria }) {
  const comps = report?.competitors ?? [];
  const ins = report?.ai.competitor_insights;
  return (
    <div className="space-y-4">
      <CriteriaBreakdown criteria={criteria} only={["competition"]} comments={report?.ai.criteria_comments} />
      {comps.length > 0 ? (
        <div className="overflow-x-auto -mx-1 px-1">
          <table className="w-full text-sm min-w-[560px]">
            <thead>
              <tr className="text-left text-xs text-zinc-500">
                <th className="font-normal py-1.5">Store</th><th className="font-normal">Price</th>
                <th className="font-normal">Offer</th><th className="font-normal">How they describe it</th>
              </tr>
            </thead>
            <tbody>
              {comps.map((c) => (
                <tr key={c.url} className="border-t border-zinc-800 align-top">
                  <td className="py-2 pr-3">
                    <a href={c.url} target="_blank" rel="noreferrer" className="text-zinc-200 hover:text-white hover:underline">{c.domain}</a>
                    {c.title && <div className="text-xs text-zinc-500 line-clamp-1">{c.title}</div>}
                  </td>
                  <td className="py-2 pr-3 tabular-nums text-zinc-200 whitespace-nowrap">
                    {c.price != null ? `${c.price} ${c.currency ?? ""}` : "—"}
                    {c.price_usd != null && c.currency !== "USD" && <div className="text-[11px] text-zinc-500">≈ {formatPrice(c.price_usd)}</div>}
                  </td>
                  <td className="py-2 pr-3">
                    <div className="flex flex-wrap gap-1">
                      {c.offer_cues.length ? c.offer_cues.map((k) => (
                        <span key={k} className="text-[11px] bg-zinc-800 text-zinc-300 rounded px-1.5 py-0.5">{CUES[k] ?? k}</span>
                      )) : <span className="text-xs text-zinc-500">—</span>}
                    </div>
                  </td>
                  <td className="py-2 text-xs text-zinc-400 max-w-[280px]"><span className="line-clamp-3">{c.description || "—"}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-[11px] text-zinc-500 mt-2">
            Observed on the stores&apos; own pages. A page existing is not proof that it sells.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          <p className="text-xs text-zinc-500">Stores advertising this product (run the AI report to read their pages):</p>
          <StoresFromAds ads={ads} />
        </div>
      )}
      {ins && (
        <div className="grid md:grid-cols-2 gap-3">
          {([["What competitors do well", ins.doing_well], ["Gaps in the market", ins.gaps],
             ["How to differentiate", ins.differentiation], ["Claims to verify", ins.unverified_claims]] as const).map(([h, items]) =>
            items.length ? (
              <div key={h} className="bg-zinc-800/40 rounded-lg p-3">
                <h4 className="text-xs font-semibold text-zinc-300 mb-2">{h}</h4>
                <Bullets items={[...items]} />
              </div>
            ) : null)}
        </div>
      )}
    </div>
  );
}

export function MarketSection({ report, criteria, market }: { report: Report | undefined; criteria: Criteria; market: { name: string; currency: string; flag?: string } }) {
  const adapt = report?.ai.market_adaptation ?? [];
  return (
    <div className="space-y-4">
      <p className="text-sm text-zinc-400">
        Target: <span className="text-zinc-200">{market.flag} {market.name}</span> · prices in {market.currency}.
        Evidence comes from ads shown to shoppers in this market — a product trending elsewhere is scored separately.
      </p>
      <CriteriaBreakdown criteria={criteria} only={["market_fit"]} comments={report?.ai.criteria_comments} />
      {report?.ai.target_audience?.length ? (
        <div>
          <h4 className="text-xs font-semibold text-zinc-300 mb-2">Who it serves</h4>
          <Bullets items={report.ai.target_audience} />
          <p className="text-sm text-zinc-400 mt-2"><span className="text-zinc-500">Problem solved:</span> {report.ai.primary_problem}</p>
        </div>
      ) : null}
      {adapt.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-zinc-300 mb-2">Adapting the offer to this market</h4>
          <ul className="space-y-1.5">
            {adapt.map((a) => (
              <li key={a.suggestion} className="flex items-start gap-2 text-sm text-zinc-300">
                <KindTag kind={a.basis === "evidence" ? "fact" : "hypothesis"} /> {a.suggestion}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export function CreativeSection({ report, criteria }: { report: Report | undefined; criteria: Criteria }) {
  const ai = report?.ai;
  return (
    <div className="space-y-4">
      <CriteriaBreakdown criteria={criteria} only={["creative", "differentiation"]} comments={ai?.criteria_comments} />
      {ai ? (
        <>
          <div>
            <h4 className="text-xs font-semibold text-zinc-300 mb-2">Ad angles</h4>
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-2">
              {ai.creative_angles.map((a) => (
                <div key={a.angle} className="bg-zinc-800/40 rounded-lg p-3">
                  <div className="text-sm text-white font-medium">{a.angle}</div>
                  <div className="text-xs text-zinc-300 mt-1">Hook: “{a.hook}”</div>
                  {a.format && <div className="text-[11px] text-zinc-500 mt-1">{a.format}</div>}
                </div>
              ))}
            </div>
          </div>
          <div className="grid md:grid-cols-2 gap-4">
            {ai.offer_ideas.length + ai.bundle_ideas.length > 0 && (
              <div>
                <h4 className="text-xs font-semibold text-zinc-300 mb-2">Offer & bundle ideas</h4>
                <Bullets items={[...ai.offer_ideas, ...ai.bundle_ideas]} />
              </div>
            )}
            {ai.product_page_headlines.length > 0 && (
              <div>
                <h4 className="text-xs font-semibold text-zinc-300 mb-2">Product page headlines</h4>
                <Bullets items={ai.product_page_headlines} />
              </div>
            )}
          </div>
          {ai.personas.length > 0 && (
            <div className="grid md:grid-cols-3 gap-2">
              {ai.personas.map((p) => (
                <div key={p.name} className="bg-zinc-800/40 rounded-lg p-3">
                  <div className="text-sm text-white font-medium">{p.name}</div>
                  <p className="text-xs text-zinc-400 mt-1">{p.description}</p>
                  {p.pain_points.length > 0 && <div className="mt-2"><Bullets items={p.pain_points} /></div>}
                </div>
              ))}
            </div>
          )}
          {ai.ugc_script && (
            <details className="bg-zinc-800/40 rounded-lg p-3 text-sm text-zinc-300">
              <summary className="cursor-pointer text-xs font-semibold text-zinc-300">UGC script (20–30 s)</summary>
              <p className="mt-2 whitespace-pre-line leading-relaxed">{ai.ugc_script}</p>
            </details>
          )}
          <p className="text-[11px] text-zinc-500">AI suggestions grounded in the product&apos;s observed features — test them, don&apos;t assume them.</p>
        </>
      ) : (
        <Empty>Run the AI report for ad angles, hooks, personas, a UGC script and offer ideas.</Empty>
      )}
    </div>
  );
}

export function SupplierSection({
  suppliers, criteria, costUsd, costEstimated, onQuote, report,
}: {
  suppliers: { platform: string; supplier_name: string; supplier_url: string; unit_cost_usd: number | null }[];
  criteria: Criteria; costUsd: number | null; costEstimated: boolean; onQuote: () => void; report: Report | undefined;
}) {
  return (
    <div className="space-y-4">
      <CriteriaBreakdown criteria={criteria} only={["logistics"]} comments={report?.ai.criteria_comments} />
      <div className="grid md:grid-cols-2 gap-4">
        <div className="space-y-2">
          <h4 className="text-xs font-semibold text-zinc-300">Supplier listings</h4>
          {suppliers?.length ? suppliers.map((s) => (
            <a key={s.supplier_url} href={s.supplier_url} target="_blank" rel="noreferrer"
               className="flex items-center justify-between gap-2 text-sm bg-zinc-800/60 hover:bg-zinc-800 rounded-lg px-3 py-2 min-h-[44px]">
              <span className="text-zinc-300">{s.supplier_name}</span>
              <span className="flex items-center gap-1 text-zinc-400">{formatPrice(s.unit_cost_usd)} <ExternalLink size={11} /></span>
            </a>
          )) : (
            <Empty>
              {costUsd != null && costEstimated
                ? `No supplier listing matched yet. The ${formatPrice(costUsd)} cost is an AI estimate.`
                : "No supplier listing matched yet."}
            </Empty>
          )}
        </div>
        <div className="bg-zinc-800/40 rounded-lg p-3 space-y-2">
          <div className="flex items-center gap-2 text-sm text-white font-medium"><Package size={14} /> Confirm before you sell</div>
          <Bullets items={["Order 2–3 samples and check quality, size and packaging",
            "Ask for the real shipping time and cost to your market", "Confirm stock levels and a backup supplier"]} />
          <button onClick={onQuote} className="mt-1 text-sm text-violet-300 hover:text-violet-200 print:hidden">Request a sourcing quote →</button>
        </div>
      </div>
    </div>
  );
}

export function RisksSection({
  weaknesses, missing, report, criteria, excluded,
}: {
  weaknesses: string[]; missing: string[]; report: Report | undefined; criteria: Criteria; excluded: string | null;
}) {
  const risks = report?.ai.risks ?? [];
  const sev = { high: "text-red-300 bg-red-500/10", medium: "text-amber-300 bg-amber-500/10", low: "text-zinc-300 bg-zinc-800" };
  return (
    <div className="space-y-4">
      {excluded && (
        <div className="flex gap-2 text-sm text-red-200 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
          <AlertTriangle size={15} className="shrink-0 mt-0.5" /> Excluded from picks: {excluded}
        </div>
      )}
      <CriteriaBreakdown criteria={criteria} only={["risk"]} comments={report?.ai.criteria_comments} />
      <div className="grid md:grid-cols-2 gap-4">
        <div>
          <h4 className="text-xs font-semibold text-zinc-300 mb-2">Weak points in the evidence</h4>
          {weaknesses?.length ? <Bullets items={weaknesses} icon={<AlertTriangle size={13} className="text-amber-400 mt-0.5 shrink-0" />} /> : <Empty>None flagged by the score.</Empty>}
        </div>
        <div>
          <h4 className="text-xs font-semibold text-zinc-300 mb-2">Not measured yet</h4>
          <Bullets items={[
            ...(missing ?? []).map((m) => `${m.replace("_", " ")} — no data, left out of the score`),
            "Search-trend volume (no source connected)",
            "Real sales or conversion rates (not visible from public ads)",
          ]} />
        </div>
      </div>
      {risks.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-zinc-300 mb-2">Risks identified by the AI report</h4>
          <ul className="space-y-1.5">
            {risks.map((r) => (
              <li key={r.description} className="flex items-start gap-2 text-sm text-zinc-300">
                <span className={cn("text-[10px] font-medium rounded px-1.5 py-0.5 shrink-0 capitalize", sev[r.severity])}>{r.severity}</span>
                <span className="text-zinc-500 capitalize shrink-0">{r.area}</span>
                <span>{r.description}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
