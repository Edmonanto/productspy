"use client";

import { useState } from "react";
import useSWR from "swr";
import { Check, Copy, Pause, Play, Plus, Wallet } from "lucide-react";
import Topbar from "@/components/layout/Topbar";
import { AdminPartner, partnersApi } from "@/lib/api";
import { cn } from "@/lib/utils";

const usd = (n: number) => n.toLocaleString("en-US", { style: "currency", currency: "USD" });

function NewPartner({ onDone }: { onDone: () => void }) {
  const [f, setF] = useState({ name: "", email: "", code: "", commission_pct: 30, commission_months: 12, discount_pct: 25 });
  const [msg, setMsg] = useState<string | null>(null);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setF({ ...f, [k]: ["name", "email", "code"].includes(k) ? e.target.value : Number(e.target.value) });
  return (
    <form className="grid sm:grid-cols-2 lg:grid-cols-6 gap-2 items-end" onSubmit={async (e) => {
      e.preventDefault(); setMsg(null);
      try {
        const r = await partnersApi.adminCreate({ ...f, code: f.code.toUpperCase() });
        setMsg(`Created — link: ${r.link}`); setF({ ...f, name: "", email: "", code: "" }); onDone();
      } catch (err) { setMsg((err as Error).message); }
    }}>
      {([["name", "Coach name", "text"], ["email", "Email (their login)", "email"], ["code", "Code (e.g. COACHMIKE)", "text"]] as const).map(([k, l, t]) => (
        <label key={k} className="block lg:col-span-1">
          <span className="text-[11px] text-zinc-400">{l}</span>
          <input required type={t} value={f[k]} onChange={set(k)}
                 className="mt-1 w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white" />
        </label>
      ))}
      {([["commission_pct", "Commission %"], ["commission_months", "Months"], ["discount_pct", "Student discount %"]] as const).map(([k, l]) => (
        <label key={k} className="block">
          <span className="text-[11px] text-zinc-400">{l}</span>
          <input type="number" min={0} max={k === "commission_months" ? 120 : 90} value={f[k]} onChange={set(k)}
                 className="mt-1 w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white" />
        </label>
      ))}
      <button className="sm:col-span-2 lg:col-span-6 flex items-center justify-center gap-1.5 bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium rounded-lg px-4 py-2.5">
        <Plus size={15} /> Add partner
      </button>
      {msg && <p className="sm:col-span-2 lg:col-span-6 text-xs text-zinc-300 break-all">{msg}</p>}
    </form>
  );
}

function Row({ p, onChange }: { p: AdminPartner; onChange: () => void }) {
  const [copied, setCopied] = useState(false);
  return (
    <tr className="border-t border-zinc-800 align-top">
      <td className="py-2.5 px-2">
        <div className="text-white font-medium">{p.name}</div>
        <div className="text-[11px] text-zinc-500">{p.email}{p.linked ? " · signed in" : " · not signed in yet"}</div>
      </td>
      <td className="px-2">
        <button onClick={async () => { try { await navigator.clipboard.writeText(p.link); setCopied(true); setTimeout(() => setCopied(false), 1200); } catch {} }}
                className="flex items-center gap-1 text-xs text-violet-300 hover:text-violet-200" title={p.link}>
          {copied ? <Check size={12} /> : <Copy size={12} />} {p.code}
        </button>
        <div className="text-[11px] text-zinc-500">{p.commission_pct}% · {p.commission_months}mo · −{p.discount_pct}%</div>
      </td>
      <td className="px-2 tabular-nums text-zinc-300 text-xs">{p.clicks} → {p.stats.signups} → {p.stats.customers}</td>
      <td className="px-2 tabular-nums text-zinc-300 text-xs">{usd(p.stats.revenue)}</td>
      <td className="px-2 tabular-nums text-xs">
        <span className="text-sky-300">{usd(p.stats.payable)}</span>
        <span className="text-zinc-500"> · hold {usd(p.stats.on_hold)} · paid {usd(p.stats.paid)}</span>
      </td>
      <td className="px-2 text-[11px] text-zinc-400 max-w-[160px]">
        {p.payout_method ? <><b className="text-zinc-300 capitalize">{p.payout_method}</b> {p.payout_details}</> : "—"}
      </td>
      <td className="px-2">
        <button onClick={async () => { await partnersApi.adminUpdate(p.id, { status: p.status === "active" ? "paused" : "active" }); onChange(); }}
                className={cn("flex items-center gap-1 text-xs rounded-md px-2 py-1", p.status === "active" ? "text-zinc-300 hover:bg-zinc-800" : "text-amber-300 bg-amber-500/10")}>
          {p.status === "active" ? <><Pause size={12} /> Pause</> : <><Play size={12} /> Resume</>}
        </button>
      </td>
    </tr>
  );
}

export default function PartnersAdminPage() {
  const { data, error, mutate } = useSWR("partners-admin", partnersApi.adminList);
  const { data: pay, mutate: mutatePay } = useSWR("partners-payouts", partnersApi.payouts);
  const [refs, setRefs] = useState<Record<string, string>>({});
  const refresh = () => { mutate(); mutatePay(); };

  return (
    <div className="flex flex-col min-h-full">
      <Topbar title="Partners (admin)" />
      <div className="p-4 md:p-6 max-w-6xl w-full mx-auto space-y-5">
        {error ? <p className="text-red-300 text-sm">{(error as Error).message}</p> : (
          <>
            <section className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-3">
              <h2 className="text-white font-semibold text-sm">Add a partner</h2>
              <NewPartner onDone={refresh} />
            </section>

            <section className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-3">
              <h2 className="text-white font-semibold text-sm flex items-center gap-2"><Wallet size={15} /> Ready to pay</h2>
              {pay?.payouts.length ? pay.payouts.map((o) => (
                <div key={o.affiliate_id + o.currency} className="flex flex-col md:flex-row md:items-center gap-2 bg-zinc-800/50 rounded-lg p-3">
                  <div className="flex-1 min-w-0">
                    <div className="text-white text-sm font-medium">{o.name} · <span className="text-sky-300">{o.total.toFixed(2)} {o.currency.toUpperCase()}</span>
                      <span className="text-zinc-500 text-xs"> ({o.payments} payments)</span></div>
                    <div className="text-xs text-zinc-400 break-all">{o.payout_method ? `${o.payout_method}: ${o.payout_details}` : "No payout details yet — ask the partner to add them"}</div>
                  </div>
                  <input placeholder="Payment reference" value={refs[o.affiliate_id] ?? ""} onChange={(e) => setRefs({ ...refs, [o.affiliate_id]: e.target.value })}
                         className="bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white md:w-48" />
                  <button disabled={(refs[o.affiliate_id] ?? "").length < 2}
                          onClick={async () => { await partnersApi.markPaid(o.affiliate_id, refs[o.affiliate_id]); refresh(); }}
                          className="bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 text-white text-sm font-medium rounded-lg px-4 py-2">
                    Mark as paid
                  </button>
                </div>
              )) : <p className="text-zinc-500 text-sm">Nothing payable right now. Commissions become payable {data?.hold_days ?? 14} days after the customer pays.</p>}
            </section>

            <section className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
              <h2 className="text-white font-semibold text-sm mb-3">Partners</h2>
              {data?.partners.length ? (
                <div className="overflow-x-auto -mx-2">
                  <table className="w-full text-sm min-w-[860px]">
                    <thead><tr className="text-left text-[11px] text-zinc-500">
                      <th className="font-normal px-2 py-1">Partner</th><th className="font-normal px-2">Code / terms</th>
                      <th className="font-normal px-2">Clicks → signups → paying</th><th className="font-normal px-2">Revenue</th>
                      <th className="font-normal px-2">Payable</th><th className="font-normal px-2">Payout to</th><th className="px-2" />
                    </tr></thead>
                    <tbody>{data.partners.map((p) => <Row key={p.id} p={p} onChange={refresh} />)}</tbody>
                  </table>
                </div>
              ) : <p className="text-zinc-500 text-sm">No partners yet.</p>}
            </section>
          </>
        )}
      </div>
    </div>
  );
}
