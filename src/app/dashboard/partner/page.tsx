"use client";

import { useState } from "react";
import useSWR from "swr";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import {
  Check, Copy, DollarSign, Gift, Handshake, Hourglass, MousePointerClick, Users, Wallet,
} from "lucide-react";
import Topbar from "@/components/layout/Topbar";
import { partnersApi, PartnerMe } from "@/lib/api";
import { SITE } from "@/lib/site";
import { cn } from "@/lib/utils";

const usd = (n: number) => n.toLocaleString("en-US", { style: "currency", currency: "USD" });

function Tile({ icon: Icon, value, label, tone }: { icon: typeof Users; value: React.ReactNode; label: string; tone: string }) {
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 flex items-center gap-3">
      <div className={cn("w-10 h-10 rounded-xl flex items-center justify-center shrink-0", tone)}><Icon size={18} /></div>
      <div className="min-w-0">
        <div className="text-xl font-extrabold text-white tabular-nums leading-none">{value}</div>
        <div className="text-[11px] text-zinc-400 mt-1">{label}</div>
      </div>
    </div>
  );
}

function CopyLink({ link }: { link: string }) {
  const [done, setDone] = useState(false);
  return (
    <div className="flex items-stretch gap-2">
      <input readOnly value={link} aria-label="Your referral link"
             className="flex-1 min-w-0 bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2.5 text-sm text-white" />
      <button onClick={async () => { try { await navigator.clipboard.writeText(link); setDone(true); setTimeout(() => setDone(false), 1500); } catch {} }}
              className="flex items-center gap-1.5 bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium rounded-lg px-4">
        {done ? <Check size={15} /> : <Copy size={15} />} {done ? "Copied" : "Copy"}
      </button>
    </div>
  );
}

function PayoutForm({ p, onSaved }: { p: NonNullable<PartnerMe["partner"]>; onSaved: () => void }) {
  const [method, setMethod] = useState(p.payout_method ?? "paypal");
  const [details, setDetails] = useState(p.payout_details);
  const [msg, setMsg] = useState<string | null>(null);
  const hint = { paypal: "Your PayPal email", wise: "Your Wise email or @handle", bank: "Account name, IBAN/account number, SWIFT/BIC, bank country", other: "How you want to be paid" }[method];
  return (
    <form className="space-y-3" onSubmit={async (e) => {
      e.preventDefault(); setMsg(null);
      try { await partnersApi.setPayout(method, details); setMsg("Saved"); onSaved(); } catch (err) { setMsg((err as Error).message); }
    }}>
      <div className="flex flex-wrap gap-1.5" role="radiogroup" aria-label="Payout method">
        {(["paypal", "wise", "bank", "other"] as const).map((m) => (
          <button type="button" key={m} role="radio" aria-checked={method === m} onClick={() => setMethod(m)}
                  className={cn("px-3 py-2 rounded-lg text-sm capitalize border", method === m ? "bg-violet-600/20 border-violet-500/50 text-white" : "border-zinc-700 text-zinc-400 hover:text-white")}>
            {m === "paypal" ? "PayPal" : m === "wise" ? "Wise" : m === "bank" ? "Bank transfer" : "Other"}
          </button>
        ))}
      </div>
      <textarea value={details} onChange={(e) => setDetails(e.target.value)} rows={2} maxLength={500} required minLength={3}
                placeholder={hint} aria-label="Payout details"
                className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white placeholder:text-zinc-500" />
      <div className="flex items-center gap-3">
        <button className="bg-zinc-800 hover:bg-zinc-700 text-white text-sm font-medium rounded-lg px-4 py-2">Save payout details</button>
        {msg && <span className="text-xs text-zinc-400">{msg}</span>}
      </div>
    </form>
  );
}

const STATUS = {
  on_hold: { label: "On hold", tone: "text-amber-300 bg-amber-500/10" },
  payable: { label: "Payable", tone: "text-sky-300 bg-sky-500/10" },
  paid: { label: "Paid", tone: "text-emerald-300 bg-emerald-500/10" },
  void: { label: "Refunded", tone: "text-zinc-400 bg-zinc-800" },
};

export default function PartnerPage() {
  const { data, error, isLoading, mutate } = useSWR("partners-me", partnersApi.me);
  const p = data?.partner;

  return (
    <div className="flex flex-col min-h-full">
      <Topbar title="Partner program" />
      <div className="p-4 md:p-6 max-w-5xl w-full mx-auto space-y-5">
        {error ? <p className="text-red-300 text-sm">{(error as Error).message}</p>
          : isLoading || !data ? <div className="h-64 bg-zinc-900 rounded-xl animate-pulse" />
          : !p ? (
            <div className="bg-gradient-to-br from-violet-950/60 to-zinc-900 border border-violet-800/30 rounded-2xl p-6 md:p-8 space-y-4">
              <Handshake className="text-violet-300" size={32} />
              <h2 className="text-white text-xl font-semibold">Earn 30% for 12 months</h2>
              <ul className="grid sm:grid-cols-3 gap-3 text-sm">
                {[["Share your link", MousePointerClick], ["Students get 25% off", Gift], ["You earn 30% of every payment", DollarSign]].map(([t, I]) => {
                  const Icon = I as typeof Users;
                  return <li key={t as string} className="flex items-center gap-2 bg-zinc-900/70 rounded-lg p-3 text-zinc-200"><Icon size={16} className="text-violet-300" /> {t as string}</li>;
                })}
              </ul>
              <p className="text-zinc-400 text-sm">For dropshipping coaches, communities and creators.</p>
              <a href={`mailto:${SITE.supportEmail}?subject=ProductSpy%20partner%20program`}
                 className="inline-block bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium rounded-lg px-4 py-2.5">Apply to become a partner</a>
              {data.referred_by && <p className="text-xs text-zinc-500">You joined through {data.referred_by.partner}.</p>}
            </div>
          ) : (
            <>
              <section className="bg-gradient-to-br from-violet-950/60 to-zinc-900 border border-violet-800/30 rounded-2xl p-5 space-y-3">
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <h2 className="text-white font-semibold text-lg">Hi {p.name.split(" ")[0]} 👋</h2>
                  <div className="flex flex-wrap gap-1.5 text-xs">
                    <span className="bg-zinc-900/80 rounded-full px-2.5 py-1 text-zinc-200"><b>{p.commission_pct}%</b> for {p.commission_months} months</span>
                    <span className="bg-zinc-900/80 rounded-full px-2.5 py-1 text-zinc-200">Students: <b>{p.discount_pct}% off</b> month 1</span>
                    <span className="bg-zinc-900/80 rounded-full px-2.5 py-1 text-zinc-200">Code <b>{p.code}</b></span>
                    {p.status === "paused" && <span className="bg-amber-500/20 text-amber-200 rounded-full px-2.5 py-1">Paused</span>}
                  </div>
                </div>
                <CopyLink link={p.link} />
              </section>

              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                <Tile icon={MousePointerClick} value={p.clicks} label="Link clicks" tone="bg-sky-600/20 text-sky-300" />
                <Tile icon={Users} value={p.stats.signups} label="Signups" tone="bg-violet-600/20 text-violet-300" />
                <Tile icon={DollarSign} value={p.stats.customers} label="Paying customers" tone="bg-emerald-600/20 text-emerald-300" />
                <Tile icon={Wallet} value={usd(p.stats.paid)} label="Paid to you" tone="bg-amber-500/20 text-amber-300" />
              </div>

              <div className="grid lg:grid-cols-3 gap-4">
                <section className="lg:col-span-2 bg-zinc-900 border border-zinc-800 rounded-xl p-4">
                  <h3 className="text-white text-sm font-semibold mb-3">Earnings by month</h3>
                  {p.monthly.length ? (
                    <div className="h-52">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={p.monthly} margin={{ left: -12, right: 4, top: 4, bottom: 0 }}>
                          <XAxis dataKey="month" tick={{ fill: "#a1a1aa", fontSize: 11 }} tickLine={false} axisLine={false} />
                          <YAxis tick={{ fill: "#a1a1aa", fontSize: 11 }} tickLine={false} axisLine={false} tickFormatter={(v) => `$${v}`} />
                          <Tooltip contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", fontSize: 12 }} formatter={(v: number) => [usd(v), "Earned"]} />
                          <Bar dataKey="earned" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  ) : <p className="text-zinc-500 text-sm py-10 text-center">Your first commission appears here when a student pays.</p>}
                </section>
                <section className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-3">
                  <h3 className="text-white text-sm font-semibold">Balance</h3>
                  {[["Payable now", p.stats.payable, "text-sky-300", Wallet], [`On hold (${p.hold_days}-day refund window)`, p.stats.on_hold, "text-amber-300", Hourglass],
                    ["Paid so far", p.stats.paid, "text-emerald-300", Check]].map(([l, v, t, I]) => {
                    const Icon = I as typeof Users;
                    return (
                      <div key={l as string} className="flex items-center justify-between gap-2 bg-zinc-800/50 rounded-lg px-3 py-2.5">
                        <span className="flex items-center gap-2 text-xs text-zinc-400"><Icon size={14} /> {l as string}</span>
                        <span className={cn("font-semibold tabular-nums", t as string)}>{usd(v as number)}</span>
                      </div>
                    );
                  })}
                  <p className="text-[11px] text-zinc-500">Payouts are sent monthly once the refund window has passed.</p>
                </section>
              </div>

              <section className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-3">
                <h3 className="text-white text-sm font-semibold">How you get paid</h3>
                <PayoutForm p={p} onSaved={() => mutate()} />
              </section>

              <section className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
                <h3 className="text-white text-sm font-semibold mb-3">Commissions</h3>
                {p.recent.length ? (
                  <div className="overflow-x-auto -mx-1">
                    <table className="w-full text-sm min-w-[420px]">
                      <thead><tr className="text-left text-xs text-zinc-500"><th className="font-normal py-1.5 px-1">Date</th><th className="font-normal px-1">Payment</th><th className="font-normal px-1">You earn</th><th className="font-normal px-1">Status</th></tr></thead>
                      <tbody>
                        {p.recent.map((c) => (
                          <tr key={c.id} className="border-t border-zinc-800">
                            <td className="py-2 px-1 text-zinc-300">{new Date(c.created_at).toLocaleDateString()}</td>
                            <td className="px-1 tabular-nums text-zinc-400">{c.amount.toFixed(2)} {c.currency.toUpperCase()}</td>
                            <td className="px-1 tabular-nums text-white font-medium">{c.commission.toFixed(2)} {c.currency.toUpperCase()}</td>
                            <td className="px-1"><span className={cn("text-[11px] rounded px-1.5 py-0.5", STATUS[c.status].tone)}>{STATUS[c.status].label}</span></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : <p className="text-zinc-500 text-sm">No commissions yet.</p>}
              </section>
            </>
          )}
      </div>
    </div>
  );
}
