"use client";

import { AlertTriangle, Loader2, RefreshCw, Sparkles } from "lucide-react";
import { ResearchReport } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Bullets, KindTag } from "./Section";

const VERDICT: Record<string, { label: string; tone: string }> = {
  validate_now: { label: "Worth validating now", tone: "text-emerald-300 bg-emerald-500/10 border-emerald-500/30" },
  investigate_further: { label: "Investigate further", tone: "text-amber-300 bg-amber-500/10 border-amber-500/30" },
  monitor: { label: "Monitor", tone: "text-sky-300 bg-sky-500/10 border-sky-500/30" },
  pass: { label: "Pass for now", tone: "text-zinc-300 bg-zinc-800 border-zinc-700" },
};

interface Props {
  report: ResearchReport | null;
  quota?: { used: number; limit: number };
  busy: boolean;
  error: string | null;
  onGenerate: (refresh?: boolean) => void;
}

/** Call-to-action / status for the AI research report. */
export function ReportCTA({ report, quota, busy, error, onGenerate }: Props) {
  const pending = report?.status === "pending" || busy;
  const left = quota ? Math.max(0, quota.limit - quota.used) : null;
  return (
    <div className="flex items-center gap-2 flex-wrap print:hidden">
      {report?.status === "ready" ? (
        <button onClick={() => onGenerate(true)} disabled={pending}
                className="flex items-center gap-1.5 text-xs text-zinc-300 bg-zinc-800 hover:bg-zinc-700 rounded-lg px-3 py-2 disabled:opacity-50"
                title="Refreshes only when the daily scan has new evidence; otherwise the saved report is kept">
          <RefreshCw size={12} /> Refresh with new evidence
        </button>
      ) : (
        <button onClick={() => onGenerate(false)} disabled={pending || left === 0}
                className="flex items-center gap-1.5 text-sm font-medium text-white bg-violet-600 hover:bg-violet-500 rounded-lg px-4 py-2 disabled:opacity-50">
          {pending ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
          {pending ? "Researching… (about a minute)" : report?.status === "failed" ? "Try the AI report again" : "Run AI research"}
        </button>
      )}
      {quota && <span className="text-[11px] text-zinc-500">{left} of {quota.limit} reports left today</span>}
      {error && <span className="text-xs text-amber-300">{error}</span>}
    </div>
  );
}

/** Section 12 — the AI's recommendation, typed findings, sources and guard-rail warnings. */
export default function AIReportPanel(props: Props) {
  const { report } = props;
  const r = report?.report;
  if (!report || report.status !== "ready" || !r) {
    return (
      <div className="space-y-3">
        <p className="text-sm text-zinc-400">
          The AI report reads every ad, video, competitor page and calculation behind this product and writes a
          recommendation, risks, ad angles, an offer and next steps. Scores and money maths stay calculated by code;
          the AI only interprets them, and must cite the evidence for every finding.
        </p>
        {report?.status === "failed" && (
          <div className="text-xs text-amber-200 bg-amber-500/10 border border-amber-500/20 rounded-lg px-3 py-2">
            {report.error ?? "The report could not be completed."}
          </div>
        )}
        <ReportCTA {...props} />
      </div>
    );
  }
  const ai = r.ai;
  const v = VERDICT[ai.recommendation.verdict] ?? VERDICT.monitor;
  const src = Object.fromEntries(r.sources.map((s) => [s.id, s]));
  return (
    <div className="space-y-5">
      <div className="flex items-start gap-3 flex-wrap">
        <span className={cn("text-sm font-semibold border rounded-lg px-3 py-1.5", v.tone)}>{v.label}</span>
        <p className="text-sm text-zinc-200 flex-1 min-w-[240px] leading-relaxed">{ai.recommendation.rationale}</p>
      </div>

      <div className="grid md:grid-cols-3 gap-3 text-sm">
        {[["Demand", ai.demand_summary], ["Competition", ai.competition_summary], ["Commercial potential", ai.commercial_potential]].map(([h, t]) => (
          <div key={h} className="bg-zinc-800/40 rounded-lg p-3">
            <div className="text-xs text-zinc-500 mb-1">{h}</div>
            <p className="text-zinc-300 leading-relaxed">{t}</p>
          </div>
        ))}
      </div>

      {ai.key_findings.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-zinc-300 mb-2">Key findings</h4>
          <ul className="space-y-2">
            {ai.key_findings.map((f) => (
              <li key={f.text} className="flex items-start gap-2 text-sm text-zinc-300">
                <KindTag kind={f.type} />
                <span className="flex-1">
                  {f.text}
                  {f.sources.map((s) => src[s] && (
                    src[s].url ? (
                      <a key={s} href={src[s].url!} target="_blank" rel="noreferrer" title={src[s].label}
                         className="ml-1 text-[11px] text-violet-300 hover:underline">[{s}]</a>
                    ) : <span key={s} title={src[s].label} className="ml-1 text-[11px] text-zinc-500">[{s}]</span>
                  ))}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="grid md:grid-cols-2 gap-4">
        <div>
          <h4 className="text-xs font-semibold text-zinc-300 mb-2">Next validation steps</h4>
          <ol className="list-decimal list-inside space-y-1 text-sm text-zinc-300">
            {ai.next_validation_steps.map((s) => <li key={s}>{s}</li>)}
          </ol>
        </div>
        <div>
          <h4 className="text-xs font-semibold text-zinc-300 mb-2">Missing information</h4>
          <Bullets items={[...ai.missing_data, ...r.not_available]} />
        </div>
      </div>

      {report.warnings.length > 0 && (
        <div className="space-y-1">
          {report.warnings.map((w) => (
            <div key={w} className="flex gap-2 text-xs text-amber-200 bg-amber-500/10 border border-amber-500/20 rounded-lg px-3 py-2">
              <AlertTriangle size={13} className="shrink-0 mt-0.5" /> {w}
            </div>
          ))}
        </div>
      )}

      <details className="text-xs text-zinc-400">
        <summary className="cursor-pointer text-zinc-300">Sources ({r.sources.length})</summary>
        <ol className="mt-2 space-y-1">
          {r.sources.map((s) => (
            <li key={s.id} className="flex gap-2">
              <span className="text-zinc-500 w-8 shrink-0">{s.id}</span>
              {s.url ? <a href={s.url} target="_blank" rel="noreferrer" className="hover:text-white underline-offset-2 hover:underline truncate">{s.label}</a>
                : <span>{s.label}</span>}
            </li>
          ))}
        </ol>
      </details>

      <div className="flex items-center justify-between gap-2 flex-wrap text-[11px] text-zinc-500">
        <span>
          Generated {new Date(r.generated_at).toLocaleString()} from {r.evidence_summary.ads} ads/videos,{" "}
          {r.evidence_summary.competitor_pages} competitor pages{report.model ? ` · ${report.model}` : ""}.
          AI output — verify before spending.
        </span>
        <ReportCTA {...props} />
      </div>
    </div>
  );
}
