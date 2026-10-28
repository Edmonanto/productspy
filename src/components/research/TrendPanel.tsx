import { Area, AreaChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { cn, fmtNum, TREND } from "@/lib/utils";

interface Props {
  trend: string;
  why: string | null;
  signals: Record<string, number | number[] | null>;
  history: { date: string; total: number; paid_ads?: number; videos?: number }[];
  search?: {
    term: string; geo: string; at: string; status: string; growth: number | null; level: number | null;
    series: { date: string; value: number }[];
  } | null;
}

const SEARCH_LABEL: Record<string, { label: string; tone: string }> = {
  rising: { label: "Searches rising", tone: "text-emerald-300 bg-emerald-500/10" },
  stable: { label: "Searches steady", tone: "text-zinc-300 bg-zinc-800" },
  falling: { label: "Searches falling", tone: "text-red-300 bg-red-500/10" },
  spike: { label: "Viral spike", tone: "text-orange-300 bg-orange-500/10" },
  low: { label: "Few searches", tone: "text-zinc-400 bg-zinc-800" },
  no_data: { label: "Not enough search data", tone: "text-zinc-400 bg-zinc-800" },
};

/** 12 months of weekly Google Trends interest (relative index). */
function SearchChart({ search }: { search: NonNullable<Props["search"]> }) {
  const lab = SEARCH_LABEL[search.status] ?? SEARCH_LABEL.stable;
  const data = search.series.map((p) => ({ ...p, label: p.date.slice(5) }));
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs text-zinc-300 font-medium">Google searches for “{search.term}” · {search.geo}</span>
        <span className={cn("text-[11px] rounded px-1.5 py-0.5", lab.tone)}>{lab.label}</span>
        {search.growth != null && search.status !== "no_data" && (
          <span className="text-[11px] text-zinc-400">
            last 4 weeks {search.growth >= 1 ? "+" : ""}{Math.round(search.growth * 100 - 100)}% vs the 8 before
          </span>
        )}
      </div>
      {data.length >= 4 && (
        <div className="h-36">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ left: -24, right: 8, top: 4, bottom: 0 }}>
              <defs>
                <linearGradient id="gt" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#38bdf8" stopOpacity={0.45} />
                  <stop offset="100%" stopColor="#38bdf8" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="#27272a" vertical={false} />
              <XAxis dataKey="label" tick={{ fill: "#a1a1aa", fontSize: 10 }} tickLine={false} axisLine={false} interval="preserveStartEnd" minTickGap={28} />
              <YAxis domain={[0, 100]} tick={{ fill: "#a1a1aa", fontSize: 10 }} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", fontSize: 12 }} formatter={(v: number) => [v, "Search index"]} />
              <Area type="monotone" dataKey="value" stroke="#38bdf8" strokeWidth={2} fill="url(#gt)" isAnimationActive={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
      <p className="text-[11px] text-zinc-500">Google Trends weekly index (0–100, relative to the peak), past 12 months. Interest in searching — not sales or search volume.</p>
    </div>
  );
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
export default function TrendPanel({ trend, why, signals: rawSignals, history: rawHistory, search }: Props) {
  // Tolerate older API responses (no signals / history fields).
  const signals = rawSignals ?? {};
  const history = rawHistory ?? [];
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
        <p className="text-sm text-zinc-300 flex-1 min-w-[200px]">{why ?? (TREND[trend] ?? TREND.unknown).hint}</p>
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
      {search && search.status ? <SearchChart search={search} /> : (
        <p className="text-[11px] text-zinc-500">Google search interest is fetched for the strongest products each day.</p>
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
          The ad time series builds up as the daily scan re-checks this product. Ads, videos and searches show
          interest — not confirmed sales.
        </p>
      )}
    </div>
  );
}
