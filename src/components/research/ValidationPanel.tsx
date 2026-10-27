"use client";

import { useState } from "react";
import useSWR from "swr";
import { CheckCircle2, Circle, CircleDashed, Loader2, OctagonAlert } from "lucide-react";
import { researchApi, StepStatus, ValidationResults, ValidationStep } from "@/lib/api";
import { cn } from "@/lib/utils";

const STATUS: Record<StepStatus, { label: string; icon: typeof Circle; tone: string }> = {
  not_started: { label: "Not started", icon: Circle, tone: "text-zinc-500" },
  in_progress: { label: "In progress", icon: CircleDashed, tone: "text-amber-300" },
  completed: { label: "Completed", icon: CheckCircle2, tone: "text-emerald-400" },
  blocked: { label: "Blocked", icon: OctagonAlert, tone: "text-red-400" },
};

function Step({ productId, step, onSaved }: { productId: string; step: ValidationStep; onSaved: () => void }) {
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<StepStatus>(step.status);
  const [notes, setNotes] = useState(step.notes);
  const [links, setLinks] = useState(step.links.join("\n"));
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const S = STATUS[status];

  const save = async (next?: StepStatus) => {
    setSaving(true); setErr(null);
    try {
      const st = next ?? status;
      await researchApi.setStep(productId, step.stage, {
        status: st, notes, links: links.split(/\s+/).map((l) => l.trim()).filter(Boolean),
      });
      setStatus(st);
      onSaved();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <li className="border border-zinc-800 rounded-lg">
      <div className="flex items-center gap-3 px-3 py-2 min-h-[48px]">
        <S.icon size={16} className={cn("shrink-0", S.tone)} aria-hidden />
        <button onClick={() => setOpen(!open)} aria-expanded={open}
                className="flex-1 text-left text-sm text-zinc-200 hover:text-white">
          {step.label}
          {step.notes && !open && <span className="block text-xs text-zinc-500 truncate">{step.notes}</span>}
        </button>
        <select aria-label={`Status of ${step.label}`} value={status} disabled={saving}
                onChange={(e) => save(e.target.value as StepStatus)}
                className="bg-zinc-800 border border-zinc-700 rounded-md px-2 py-1.5 text-xs text-zinc-200 print:hidden">
          {Object.entries(STATUS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
        </select>
      </div>
      {open && (
        <div className="px-3 pb-3 space-y-2">
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} maxLength={4000}
                    placeholder="Notes, findings, supplier replies…" aria-label="Notes"
                    className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white placeholder:text-zinc-500" />
          <textarea value={links} onChange={(e) => setLinks(e.target.value)} rows={2}
                    placeholder="Source links (one per line)" aria-label="Source links"
                    className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-xs text-white placeholder:text-zinc-500" />
          <div className="flex items-center gap-2">
            <button onClick={() => save()} disabled={saving}
                    className="text-xs font-medium bg-violet-600 hover:bg-violet-500 text-white rounded-lg px-3 py-2 disabled:opacity-50">
              {saving ? "Saving…" : "Save"}
            </button>
            {err && <span className="text-xs text-red-300">{err}</span>}
          </div>
        </div>
      )}
    </li>
  );
}

const RESULT_FIELDS: { key: keyof ValidationResults; label: string; money?: boolean }[] = [
  { key: "supplier_quote_usd", label: "Supplier quote / unit", money: true },
  { key: "shipping_quote_usd", label: "Shipping quote / order", money: true },
  { key: "selling_price_usd", label: "Your selling price", money: true },
  { key: "ad_spend_usd", label: "Test ad spend", money: true },
  { key: "orders", label: "Orders" },
  { key: "revenue_usd", label: "Revenue", money: true },
  { key: "refunds", label: "Refunds" },
];

function Results({ productId, initial, onSaved }: { productId: string; initial: ValidationResults; onSaved: () => void }) {
  const [v, setV] = useState<ValidationResults>(initial);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const save = async () => {
    setSaving(true); setErr(null);
    try { await researchApi.setResults(productId, v); onSaved(); }
    catch (e) { setErr((e as Error).message); }
    finally { setSaving(false); }
  };
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
        {RESULT_FIELDS.map((f) => (
          <label key={f.key} className="block">
            <span className="text-[11px] text-zinc-400">{f.label} {f.money && "(USD)"}</span>
            <input type="number" min={0} step={f.money ? "0.01" : "1"} inputMode="decimal"
                   value={(v[f.key] as number | null | undefined) ?? ""}
                   onChange={(e) => setV({ ...v, [f.key]: e.target.value === "" ? null : Number(e.target.value) })}
                   className="mt-1 w-full bg-zinc-800 border border-zinc-700 rounded-lg px-2.5 py-2 text-sm text-white" />
          </label>
        ))}
        <label className="block">
          <span className="text-[11px] text-zinc-400">Decision</span>
          <select value={v.decision ?? ""} onChange={(e) => setV({ ...v, decision: (e.target.value || null) as ValidationResults["decision"] })}
                  className="mt-1 w-full bg-zinc-800 border border-zinc-700 rounded-lg px-2.5 py-2 text-sm text-white">
            <option value="">Not decided</option><option value="launch">Launch</option>
            <option value="iterate">Iterate</option><option value="drop">Drop</option>
          </select>
        </label>
      </div>
      <div className="flex items-center gap-2 print:hidden">
        <button onClick={save} disabled={saving}
                className="text-xs font-medium bg-zinc-800 hover:bg-zinc-700 text-white rounded-lg px-3 py-2 disabled:opacity-50">
          {saving ? "Saving…" : "Save my results"}
        </button>
        {err && <span className="text-xs text-red-300">{err}</span>}
      </div>
    </div>
  );
}

/** Section 11 — the user's own step-by-step validation, and their real numbers against the research. */
export default function ValidationPanel({ productId }: { productId: string }) {
  const { data, error, isLoading, mutate } = useSWR(["validation", productId], () => researchApi.validation(productId));
  if (error) return <p className="text-sm text-red-300">{(error as Error).message}</p>;
  if (isLoading || !data) return <div className="flex items-center gap-2 text-sm text-zinc-500"><Loader2 size={14} className="animate-spin" /> Loading your checklist…</div>;
  const pct = Math.round((data.progress.completed / data.progress.total) * 100);
  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <div className="flex-1 h-2 bg-zinc-800 rounded-full overflow-hidden" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
          <div className="h-full bg-violet-500 rounded-full" style={{ width: `${pct}%` }} />
        </div>
        <span className="text-xs text-zinc-400 tabular-nums">{data.progress.completed}/{data.progress.total} done</span>
      </div>
      <p className="text-xs text-zinc-500">A high score isn&apos;t a launch decision. Work through each stage; only you can see this checklist.</p>
      <ol className="space-y-2">
        {data.steps.map((s) => <Step key={s.stage} productId={productId} step={s} onSaved={() => mutate()} />)}
      </ol>
      <div className="border-t border-zinc-800 pt-4 space-y-3">
        <h4 className="text-sm text-white font-semibold">Your real numbers vs. the research</h4>
        <Results productId={productId} initial={data.results} onSaved={() => mutate()} />
        {data.comparison && (data.comparison.notes.length > 0 || Object.keys(data.comparison.actual).length > 0) && (
          <div className="bg-zinc-800/40 rounded-lg p-3 space-y-2 text-sm">
            <div className="flex flex-wrap gap-4 text-xs text-zinc-400">
              {data.comparison.actual.cpa_usd != null && <span>Actual CPA <b className="text-white">${data.comparison.actual.cpa_usd}</b></span>}
              {data.comparison.actual.roas != null && <span>Actual ROAS <b className="text-white">{data.comparison.actual.roas}×</b></span>}
              {data.comparison.actual.refund_rate_pct != null && <span>Refund rate <b className="text-white">{data.comparison.actual.refund_rate_pct}%</b></span>}
              {data.comparison.actual.contribution_after_ads_usd != null && (
                <span>Profit / order after ads <b className={data.comparison.actual.contribution_after_ads_usd < 0 ? "text-red-400" : "text-emerald-400"}>
                  ${data.comparison.actual.contribution_after_ads_usd}</b></span>
              )}
            </div>
            <ul className="space-y-1 text-zinc-300">{data.comparison.notes.map((n) => <li key={n}>• {n}</li>)}</ul>
          </div>
        )}
      </div>
    </div>
  );
}
