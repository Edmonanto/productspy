"use client";

import { useState } from "react";
import useSWR from "swr";
import Topbar from "@/components/layout/Topbar";
import { funnelApi } from "@/lib/api";
import { cn } from "@/lib/utils";

const STEP_LABEL: Record<string, [string, string]> = {
  landing_view: ["Landing visits", "Home page loads (/ or /fr)"],
  signup_click: ["Signup clicks", "Clicks on a sign-up button"],
  account_created: ["Accounts created", "First visit to the dashboard"],
  winner_opened: ["Opened a winner", "Looked at a product page at least once"],
  checkout_started: ["Started checkout", "Opened Stripe or PayPal checkout"],
  paid: ["Paid", "Paid plan with a card on file (incl. paying during the trial)"],
};
const LANGS = [["en", "🇬🇧 English"], ["fr", "🇫🇷 French"]] as const;
const RANGES = [7, 30, 90];

function pct(n: number, of: number) {
  return of > 0 ? `${Math.round((n / of) * 1000) / 10}%` : "—";
}

export default function FunnelPage() {
  const [days, setDays] = useState(30);
  const { data, error, isLoading } = useSWR(["funnel", days], () => funnelApi.summary(days));

  const steps = data?.steps ?? [];
  const col = (lang: string | null) => steps.map((s) => (lang ? s.by_lang[lang] ?? 0 : s.total));

  return (
    <>
      <Topbar title="Signup funnel" />
      <div className="p-4 md:p-6 space-y-5 max-w-5xl">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-zinc-400 max-w-2xl">
            Each step counts what happened in the period. Signed-in steps count each user once and use the
            language they signed up in. Visits and clicks are anonymous (no cookie).
          </p>
          <div className="flex gap-1 bg-zinc-900 border border-zinc-800 rounded-lg p-1">
            {RANGES.map((d) => (
              <button key={d} onClick={() => setDays(d)}
                      className={cn("px-3 py-1.5 rounded-md text-xs font-semibold", d === days ? "bg-violet-600 text-white" : "text-zinc-400 hover:text-white")}>
                {d} days
              </button>
            ))}
          </div>
        </div>

        {error ? (
          <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300">{(error as Error).message}</div>
        ) : isLoading || !data ? (
          <div className="h-64 rounded-xl bg-zinc-900 border border-zinc-800 animate-pulse" />
        ) : (
          <div className="rounded-xl border border-zinc-800 overflow-x-auto">
            <table className="w-full text-sm min-w-[560px]">
              <thead className="bg-zinc-900 text-xs text-zinc-400">
                <tr>
                  <th className="text-left font-medium p-3">Step</th>
                  {LANGS.map(([, l]) => <th key={l} className="text-right font-medium p-3">{l}</th>)}
                  <th className="text-right font-medium p-3">All</th>
                </tr>
              </thead>
              <tbody>
                {steps.map((s, i) => {
                  const [label, hint] = STEP_LABEL[s.event] ?? [s.event, ""];
                  return (
                    <tr key={s.event} className="border-t border-zinc-800">
                      <td className="p-3">
                        <div className="text-white font-medium">{label}</div>
                        <div className="text-[11px] text-zinc-500">{hint}</div>
                      </td>
                      {[...LANGS.map(([k]) => k), null].map((lang) => {
                        const c = col(lang);
                        return (
                          <td key={lang ?? "all"} className="p-3 text-right tabular-nums">
                            <div className="text-white font-semibold">{c[i].toLocaleString("en-US")}</div>
                            {i > 0 && <div className="text-[11px] text-zinc-500">{pct(c[i], c[i - 1])} of previous</div>}
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {data && data.signup_click_sources.length > 0 && (
          <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
            <h3 className="text-sm font-semibold text-white mb-3">Which sign-up buttons get clicked</h3>
            <div className="grid sm:grid-cols-2 gap-x-6 gap-y-1.5">
              {data.signup_click_sources.map((r) => (
                <div key={`${r.lang}-${r.source}`} className="flex justify-between text-sm">
                  <span className="text-zinc-400">{r.lang === "fr" ? "🇫🇷" : r.lang === "en" ? "🇬🇧" : "?"} {r.source.replace("_", " ")}</span>
                  <span className="text-white tabular-nums">{r.n}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </>
  );
}
