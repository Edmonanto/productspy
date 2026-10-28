"use client";

/** Visual building blocks: product picture (or a category illustration), radar, trend icon, metric chips. */
import Link from "next/link";
import {
  Baby, Car, Lightbulb, Dumbbell, Gem, HeartPulse, Home, Laptop, Minus, Package, PawPrint, Shirt, Sparkles, Tent,
  TrendingDown, TrendingUp, UtensilsCrossed, Wrench, Puzzle, Snowflake, Zap, HelpCircle, LucideIcon,
} from "lucide-react";
import { PolarAngleAxis, PolarGrid, Radar, RadarChart, ResponsiveContainer } from "recharts";
import ProductImage from "@/components/products/ProductImage";
import { Breakdown, WinnerPick } from "@/lib/api";
import { cn, CriterionKey, PILLAR_MAX, TREND } from "@/lib/utils";

const CATEGORY: Record<string, { icon: LucideIcon; from: string; to: string }> = {
  home: { icon: Home, from: "#4c1d95", to: "#1e1b4b" },
  kitchen: { icon: UtensilsCrossed, from: "#9a3412", to: "#431407" },
  beauty: { icon: Sparkles, from: "#9d174d", to: "#500724" },
  health: { icon: HeartPulse, from: "#065f46", to: "#022c22" },
  fitness: { icon: Dumbbell, from: "#1e40af", to: "#172554" },
  pets: { icon: PawPrint, from: "#854d0e", to: "#422006" },
  baby: { icon: Baby, from: "#0e7490", to: "#083344" },
  "kids-toys": { icon: Puzzle, from: "#a16207", to: "#422006" },
  "fashion-accessories": { icon: Gem, from: "#7e22ce", to: "#3b0764" },
  fashion: { icon: Shirt, from: "#7e22ce", to: "#3b0764" },
  "tech-gadgets": { icon: Laptop, from: "#334155", to: "#0f172a" },
  car: { icon: Car, from: "#b91c1c", to: "#450a0a" },
  outdoor: { icon: Tent, from: "#15803d", to: "#052e16" },
  tools: { icon: Wrench, from: "#52525b", to: "#18181b" },
};

/** Product photo; without one, a category illustration instead of an empty box. */
export function ProductVisual({ src, alt, category, className, iconSize = 28 }: {
  src: string | null | undefined; alt: string; category?: string | null; className?: string; iconSize?: number;
}) {
  const c = CATEGORY[category ?? ""] ?? { icon: Package, from: "#3f3f46", to: "#18181b" };
  const Icon = c.icon;
  return (
    <div className={cn("relative overflow-hidden bg-zinc-800", className)}>
      <ProductImage src={src ?? null} alt={alt} className="w-full h-full object-cover"
        fallback={
          <div className="w-full h-full flex items-center justify-center" style={{ background: `linear-gradient(135deg, ${c.from}, ${c.to})` }}
               role="img" aria-label={alt}>
            <Icon size={iconSize} className="text-white/70" strokeWidth={1.5} />
          </div>
        } />
    </div>
  );
}

const TREND_ICON: Record<string, LucideIcon> = {
  emerging: Zap, growing: TrendingUp, stable: Minus, declining: TrendingDown, seasonal: Snowflake, unknown: HelpCircle,
};

/** Trend as an icon (label in the tooltip / for screen readers). */
export function TrendIcon({ trend, size = 14, withLabel = false, className }: { trend?: string | null; size?: number; withLabel?: boolean; className?: string }) {
  const t = TREND[trend ?? "unknown"] ?? TREND.unknown;
  const Icon = TREND_ICON[trend ?? "unknown"] ?? HelpCircle;
  return (
    <span title={`${t.label} — ${t.hint}`} className={cn("inline-flex items-center gap-1 border rounded-full px-1.5 py-0.5 text-[11px] font-medium", t.tone, className)}>
      <Icon size={size} aria-hidden />
      {withLabel ? t.label : <span className="sr-only">{t.label}</span>}
    </span>
  );
}

export const SHORT_LABEL: Record<CriterionKey, string> = {
  demand: "Demand", profitability: "Profit", competition: "Competition", creative: "Creative",
  differentiation: "Offer", logistics: "Logistics", market_fit: "Market", risk: "Risk",
};

/** 8-criteria radar, each axis as % of its maximum. Unknown criteria sit at 0 and are greyed. */
export function CriteriaRadar({ breakdown, size = 220, compact = false }: { breakdown?: Breakdown; size?: number; compact?: boolean }) {
  const data = (Object.keys(PILLAR_MAX) as CriterionKey[]).map((k) => {
    const v = breakdown?.[k];
    return { k: SHORT_LABEL[k] + (v == null ? " ?" : ""), v: v == null ? 0 : Math.round((v / PILLAR_MAX[k]) * 100) };
  });
  return (
    <div style={{ height: size }} className="w-full" role="img"
         aria-label={`Criteria: ${data.map((d) => `${d.k} ${d.v}%`).join(", ")}`}>
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data} outerRadius={compact ? "70%" : "72%"} margin={{ top: 4, right: 18, bottom: 4, left: 18 }}>
          <PolarGrid stroke="#3f3f46" />
          <PolarAngleAxis dataKey="k" tick={{ fill: "#a1a1aa", fontSize: compact ? 9 : 11 }} />
          <Radar dataKey="v" stroke="#a78bfa" fill="#8b5cf6" fillOpacity={0.35} strokeWidth={2} isAnimationActive={false} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Small icon + value chip. */
export function Chip({ icon: Icon, value, title, tone = "text-zinc-200" }: { icon: LucideIcon; value: React.ReactNode; title: string; tone?: string }) {
  return (
    <span title={title} className="inline-flex items-center gap-1 bg-black/50 backdrop-blur border border-white/10 rounded-full px-2 py-0.5 text-[11px] font-semibold">
      <Icon size={11} className="text-zinc-400" aria-hidden />
      <span className={tone}>{value}</span>
      <span className="sr-only">{title}</span>
    </span>
  );
}

function scoreTone(s: number) {
  return s >= 70 ? "bg-emerald-500 text-emerald-950" : s >= 55 ? "bg-amber-400 text-amber-950" : "bg-zinc-600 text-white";
}

/** Picture-first tile for a pick: image, score badge, trend, margin, stores. */
export function PickTile({ pick, market, big = false }: { pick: WinnerPick; market: string; big?: boolean }) {
  const p = pick.product!;
  const margin = pick.economics?.complete ? pick.economics.contribution_margin_pct : null;
  return (
    <Link href={`/dashboard/winners/${p.id}?market=${market}`}
          className="group block bg-zinc-900 border border-zinc-800 hover:border-violet-500/50 rounded-xl overflow-hidden transition-colors">
      <div className="relative">
        <ProductVisual src={p.image_url} alt={p.title} category={p.category} iconSize={big ? 48 : 32}
                       className={cn("w-full", big ? "aspect-[4/3]" : "aspect-square")} />
        <span className="absolute top-2 left-2 w-7 h-7 rounded-full bg-black/60 backdrop-blur text-white text-xs font-bold flex items-center justify-center">{pick.rank}</span>
        <span className={cn("absolute top-2 right-2 rounded-lg px-2 py-1 text-sm font-extrabold tabular-nums shadow", scoreTone(pick.total))}
              title={`Score ${pick.total}/100`}>{pick.total}</span>
        <div className="absolute bottom-2 left-2 right-2 flex flex-wrap gap-1">
          <TrendIcon trend={pick.trend} className="bg-black/50 backdrop-blur" />
          {margin != null && <Chip icon={TrendingUp} value={`${Math.round(margin)}%`} title="Margin before ads" tone={margin >= 30 ? "text-emerald-300" : "text-amber-300"} />}
          {!!pick.stats?.stores && <Chip icon={Home} value={pick.stats.stores} title="Stores advertising it" />}
        </div>
      </div>
      <div className="px-3 py-2.5">
        <div className="text-sm text-zinc-100 font-medium line-clamp-1 group-hover:text-white">{p.title}</div>
        <div className="text-xs text-zinc-500 tabular-nums">{p.price_usd != null ? `$${p.price_usd.toFixed(2)}` : "—"}</div>
        {pick.angles?.[0] && (
          <div className="mt-1.5 flex items-start gap-1 text-[11px] text-violet-200/90" title={`Hook: “${pick.angles[0].hook}”`}>
            <Lightbulb size={12} className="shrink-0 mt-px text-violet-300" aria-hidden />
            <span className="line-clamp-1">{pick.angles[0].angle}</span>
          </div>
        )}
      </div>
    </Link>
  );
}

/** Suggested ad angles: name, 3-second hook, format. */
export function AngleList({ angles, compact = false }: { angles?: { angle: string; hook: string; format?: string; audience?: string }[]; compact?: boolean }) {
  if (!angles?.length) return null;
  return (
    <div className={cn("grid gap-2", compact ? "grid-cols-1" : "md:grid-cols-3")}>
      {angles.map((a) => (
        <div key={a.angle} className="bg-violet-500/5 border border-violet-500/20 rounded-lg p-3">
          <div className="flex items-center gap-1.5 text-sm text-white font-medium">
            <Lightbulb size={14} className="text-violet-300 shrink-0" aria-hidden /> {a.angle}
          </div>
          <div className="text-xs text-zinc-300 mt-1">“{a.hook}”</div>
          {(a.format || a.audience) && (
            <div className="flex flex-wrap gap-1 mt-2">
              {a.format && <span className="text-[10px] bg-zinc-800 text-zinc-300 rounded px-1.5 py-0.5">{a.format}</span>}
              {a.audience && <span className="text-[10px] bg-zinc-800 text-zinc-400 rounded px-1.5 py-0.5">{a.audience}</span>}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
