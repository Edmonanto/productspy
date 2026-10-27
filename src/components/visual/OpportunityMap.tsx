"use client";

import { useRouter } from "next/navigation";
import {
  CartesianGrid, ReferenceArea, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis,
} from "recharts";
import { WinnerPick } from "@/lib/api";
import { TREND } from "@/lib/utils";

const COLOR: Record<string, string> = {
  emerging: "#38bdf8", growing: "#34d399", stable: "#a1a1aa", declining: "#f87171", seasonal: "#fbbf24", unknown: "#71717a",
};

interface Pt { x: number; y: number; z: number; id: string; title: string; trend: string }

function Tip({ active, payload }: { active?: boolean; payload?: { payload: Pt }[] }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-xs shadow-xl">
      <div className="text-white font-medium max-w-[200px] truncate">{p.title}</div>
      <div className="text-zinc-400 mt-0.5">Score {p.y} · margin {p.x}% · {p.z} stores · {TREND[p.trend]?.label}</div>
    </div>
  );
}

/** Score (up) vs margin before ads (right): the top-right corner is where to look first. */
export default function OpportunityMap({ picks, market, height = 260 }: { picks: WinnerPick[]; market: string; height?: number }) {
  const router = useRouter();
  const pts: Pt[] = picks
    .filter((w) => w.product && w.economics?.complete && w.economics.contribution_margin_pct != null)
    .map((w) => ({
      x: Math.round(w.economics!.contribution_margin_pct!), y: w.total, z: Math.max(1, w.stats?.stores ?? 1),
      id: w.product!.id, title: w.product!.title, trend: w.trend ?? "unknown",
    }));
  if (pts.length < 2) {
    return <div className="h-full min-h-[160px] flex items-center justify-center text-zinc-500 text-xs">Needs 2+ products with a known margin</div>;
  }
  const byTrend = Object.keys(COLOR).map((t) => ({ t, data: pts.filter((p) => p.trend === t) })).filter((g) => g.data.length);
  return (
    <div style={{ height }} role="img" aria-label={`Opportunity map of ${pts.length} products: score versus margin`}>
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 8, right: 12, bottom: 4, left: -18 }}>
          <ReferenceArea x1={30} x2={100} y1={70} y2={100} fill="#10b981" fillOpacity={0.06} stroke="none" />
          <CartesianGrid stroke="#27272a" />
          <XAxis type="number" dataKey="x" name="Margin" unit="%" domain={[0, 80]} tick={{ fill: "#a1a1aa", fontSize: 10 }} tickLine={false} axisLine={false} />
          <YAxis type="number" dataKey="y" name="Score" domain={[30, 100]} tick={{ fill: "#a1a1aa", fontSize: 10 }} tickLine={false} axisLine={false} />
          <ZAxis type="number" dataKey="z" range={[60, 420]} />
          <Tooltip content={<Tip />} cursor={{ stroke: "#52525b", strokeDasharray: "3 3" }} />
          {byTrend.map((g) => (
            <Scatter key={g.t} data={g.data} fill={COLOR[g.t]} fillOpacity={0.85} isAnimationActive={false}
                     onClick={(d: Pt) => router.push(`/dashboard/winners/${d.id}?market=${market}`)} className="cursor-pointer" />
          ))}
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}

export function TrendLegend() {
  return (
    <div className="flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-zinc-400">
      {["emerging", "growing", "stable", "declining"].map((t) => (
        <span key={t} className="inline-flex items-center gap-1"><span className="w-2 h-2 rounded-full" style={{ background: COLOR[t] }} />{TREND[t].label}</span>
      ))}
      <span className="inline-flex items-center gap-1"><span className="w-3 h-2 rounded-sm bg-emerald-500/20 border border-emerald-500/30" />best zone</span>
    </div>
  );
}
