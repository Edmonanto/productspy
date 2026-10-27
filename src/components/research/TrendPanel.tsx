import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { cn, fmtNum, TREND } from "@/lib/utils";

interface Props {
  trend: string;
  why: string | null;
  signals: Record<string, number | number[] | null>;
  history: { date: string; total: number; paid_ads?: number; videos?: number }[];
}

const n = (v: unknown) => (typeof v === "number" ? v : null);

export function TrendBadge({ trend, className }: { trend?: string | null; className?: string }) {
  const t = TREND[trend ?? "unknown"] ?? TREND.unknown;
  return (
    <span title={t.hint} className={cn("text-[11px] font-medium border rounded px-1.5 py-0.5", t.tone, className)}>
      {t.label}
    </span>
  );
}

/** Demand & trend: direction, the dated signals behind it, and the time series when we have one. */
export default function TrendPanel({ trend, why, signals, history }: Props) {
  const facts: [string, string | null][] = [
    ["New ads, last 7 days", n(signals.new_creatives_7d) != null ? String(signals.new_creatives_7d) : null],
    ["New ads, last 14 days", n(signals.new_creatives_14d) != null ? String(signals.new_creatives_14d) : null],
    ["New ads, last 30 days", n(signals.new_creatives_30d) != null ? String(signals.new_creatives_30d) : null],
    ["Longest-running ad", n(signals.max_days_running) != null ? `${signals.max_days_running} days` : null],
    ["Stores advertising", n(signals.advertisers) ? String(signals.advertisers) : null],
    ["Creators posting", n(signals.creators) ? String(signals.creators) : null],
    ["Lifetime video views", n(signals.total_views) ? fmtNum(n(signals.total_views)) : null],
    ["First seen", n(signals.first_seen_days) != null ? `${signals.first_seen_days} days ago` : null],
  ];
  const shown = facts.filter(([, v]) => v != null);
  const series = history.filter((h) => h.paid_ads != null);
  return (
    <div className="space-y-4">
      <div className="flex items-start gap-3 flex-wrap">
        <TrendBadge trend={trend} className="text-xs px-2 py-1" />
        <p className="text-sm text-zinc-300 flex-1 min-w-[200px]">{why ?? TREND[trend]?.hint}</p>
      </div>
      {shown.length > 0 && (
        <dl className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {shown.map(([label, v]) => (
            <div key={label} className="bg-zinc-800/50 rounded-lg px-3 py-2">
              <dt className="text-[11px] text-zinc-500">{label}</dt>
              <dd className="text-sm text-white font-semibold tabular-nums">{v}</dd>
            </div>
          ))}
        </dl>
      )}
      {series.length >= 2 ? (
        <div>
          <div className="text-xs text-zinc-500 mb-2">
            Active paid ads and TikTok videos linked to this product on each daily scan ({series[0].date} → {series[series.length - 1].date})
          </div>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={series} margin={{ left: -20, right: 8, top: 4, bottom: 0 }}>
                <CartesianGrid stroke="#27272a" vertical={false} />
                <XAxis dataKey="date" tick={{ fill: "#a1a1aa", fontSize: 11 }} tickLine={false} axisLine={false} />
                <YAxis allowDecimals={false} tick={{ fill: "#a1a1aa", fontSize: 11 }} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", fontSize: 12 }} />
                <Legend wrapperStyle={{ fontSize: 11, color: "#a1a1aa" }} />
                <Line type="monotone" dataKey="paid_ads" name="Active paid ads" stroke="#a78bfa" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="videos" name="TikTok videos" stroke="#34d399" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      ) : (
        <p className="text-xs text-zinc-500">
          The time series builds up as the daily scan re-checks this product. Search-trend data isn&apos;t connected,
          so demand here comes from ads and videos only — interest, not confirmed sales.
        </p>
      )}
    </div>
  );
}
