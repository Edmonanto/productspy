"use client";

import { DataStatus, SourceState, SourceStatus } from "@/lib/api";
import { timeAgo } from "@/lib/utils";

interface Props {
  status: DataStatus | undefined;
  loading: boolean;
}

const SOURCE_NAMES: Record<string, string> = {
  "1688-aggregator": "1688",
  "1688": "1688 Open Platform",
  tiktok: "TikTok Shop",
  amazon: "Amazon",
  aliexpress: "AliExpress",
};

const DOT: Record<SourceState, string> = {
  ok: "bg-emerald-500",
  low_credits: "bg-yellow-500",
  out_of_credits: "bg-red-500",
  failing: "bg-yellow-500",
  never_run: "bg-zinc-600",
};

/** What a customer sees: freshness, never provider internals. */
function customerLine(s: SourceStatus): string {
  if (s.state === "never_run") return "First update pending";
  if (!s.last_success_at) return "Update delayed";
  const ago = `Updated ${timeAgo(s.last_success_at)}`;
  return s.state === "ok" || s.state === "low_credits" ? ago : `${ago} · refresh delayed`;
}

/** What an admin (ADMIN_EMAILS) additionally sees. Always a line, so an admin
 *  can tell "no data yet" apart from "not recognised as admin". */
function adminLine(s: SourceStatus): string {
  if (s.state === "out_of_credits") return "Out of credits — top up the token";
  const parts = s.endpoints.map((e) => {
    const cap = e.daily_cap != null ? `/${e.daily_cap}` : "";
    const left = e.balance != null ? `, ${e.balance} left` : "";
    return `${e.endpoint} ${e.calls_today}${cap} today${left}`;
  });
  if (s.state === "failing" && s.last_error) parts.push(`error: ${s.last_error}`);
  return parts.length
    ? parts.join(" · ")
    : "No paid calls recorded yet — the daily job runs at 02:00 UTC";
}

export default function DataStatusCard({ status, loading }: Props) {
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-white font-semibold text-sm">Data sources</h3>
        {status?.is_admin && (
          <span className="text-[10px] font-semibold uppercase tracking-wide bg-violet-600/20 text-violet-300 border border-violet-600/30 px-1.5 py-0.5 rounded">
            Admin
          </span>
        )}
      </div>

      {loading && <p className="text-zinc-600 text-xs">Checking…</p>}

      {!loading && !status && (
        <p className="text-yellow-500/80 text-xs">Couldn&apos;t load data status.</p>
      )}

      {!loading && status && !status.sources.length && (
        <p className="text-zinc-500 text-xs">
          No data source has run yet. Products update once a day.
          {status.is_admin && " No 1688 provider is configured on the API — check AGG1688_SEARCH_TOKEN and AGG1688_KEYWORDS."}
        </p>
      )}

      <div className="space-y-3">
        {status?.sources.map((s) => {
          const admin = status.is_admin ? adminLine(s) : null;
          return (
            <div key={s.provider} className="text-xs">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2 min-w-0">
                  <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${DOT[s.state]}`} />
                  <span className="text-zinc-300 truncate">{SOURCE_NAMES[s.provider] ?? s.provider}</span>
                </div>
                <span className="text-zinc-500 shrink-0">{customerLine(s)}</span>
              </div>
              {admin && (
                <p className={`mt-1 pl-3.5 break-words ${s.state === "out_of_credits" ? "text-red-400" : "text-zinc-600"}`}>
                  {admin}
                </p>
              )}
            </div>
          );
        })}
      </div>

      {status && Object.keys(status.products).length > 0 && (
        <p className="text-zinc-600 text-[11px] mt-4">
          {Object.values(status.products).reduce((a, b) => a + b, 0).toLocaleString()} products tracked · updates daily
        </p>
      )}
    </div>
  );
}
