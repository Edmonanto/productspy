import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Score colours: 70+ strong (green), 55-69 promising (amber), below that grey. */
export function scoreColor(score: number): string {
  if (score >= 70) return "text-emerald-400";
  if (score >= 55) return "text-amber-400";
  return "text-zinc-400";
}

/** Interpretation bands (backend: winners/scoring.py BANDS). Decision support, not proof. */
export function scoreBand(score: number): string {
  if (score >= 85) return "Exceptional research candidate";
  if (score >= 70) return "Strong candidate worth validating";
  if (score >= 55) return "Promising — needs further investigation";
  if (score >= 40) return "Weak or uncertain opportunity";
  return "Low priority on current evidence";
}

export const TREND: Record<string, { label: string; tone: string; hint: string }> = {
  emerging: { label: "Emerging", tone: "text-sky-300 bg-sky-500/10 border-sky-500/25", hint: "Recently appeared, new ads still launching" },
  growing: { label: "Growing", tone: "text-emerald-300 bg-emerald-500/10 border-emerald-500/25", hint: "More ads or faster views than before" },
  stable: { label: "Stable", tone: "text-zinc-300 bg-zinc-800 border-zinc-700", hint: "Ads keep running, little change" },
  declining: { label: "Declining", tone: "text-red-300 bg-red-500/10 border-red-500/25", hint: "Fewer active ads than on earlier scans" },
  seasonal: { label: "Seasonal", tone: "text-amber-300 bg-amber-500/10 border-amber-500/25", hint: "Depends on the time of year" },
  unknown: { label: "Trend unclear", tone: "text-zinc-400 bg-zinc-800 border-zinc-700", hint: "Not enough dated evidence yet" },
};

export function formatPrice(usd: number | null): string {
  if (usd == null) return "N/A";
  return `$${usd.toFixed(2)}`;
}

export function estimatedMargin(price: number | null, cost: number | null): string {
  if (!price || !cost || cost === 0) return "N/A";
  const pct = ((price - cost) / price) * 100;
  return `${pct.toFixed(0)}%`;
}


export function fmtNum(n: number | null | undefined): string {
  if (n == null) return "—";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(n >= 10_000_000 ? 0 : 1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(n >= 10_000 ? 0 : 1)}K`;
  return String(Math.round(n));
}

export function fmtPct(ratio: number | null | undefined, digits = 1): string {
  if (ratio == null) return "—";
  return `${(ratio * 100).toFixed(digits)}%`;
}

/** The eight scoring criteria and default weights (backend: winners/scoring.py CRITERIA). */
export const PILLAR_MAX = {
  demand: 20, profitability: 20, competition: 15, creative: 10,
  differentiation: 10, logistics: 10, market_fit: 10, risk: 5,
} as const;
export type CriterionKey = keyof typeof PILLAR_MAX;

export const PILLAR_LABEL: Record<CriterionKey, string> = {
  demand: "Demand & trend",
  profitability: "Profitability",
  competition: "Competition",
  creative: "Creative potential",
  differentiation: "Differentiation",
  logistics: "Logistics",
  market_fit: "Market fit",
  risk: "Risk",
};

export const EVIDENCE_KIND: Record<string, { label: string; tone: string }> = {
  observed: { label: "Observed", tone: "text-emerald-300 bg-emerald-500/10" },
  calculated: { label: "Calculated", tone: "text-sky-300 bg-sky-500/10" },
  ai: { label: "AI-assessed", tone: "text-violet-300 bg-violet-500/10" },
  assumption: { label: "Assumption", tone: "text-amber-300 bg-amber-500/10" },
  fact: { label: "Fact", tone: "text-emerald-300 bg-emerald-500/10" },
  estimate: { label: "Estimate", tone: "text-amber-300 bg-amber-500/10" },
  hypothesis: { label: "Hypothesis", tone: "text-zinc-300 bg-zinc-800" },
};

export const SOURCE_LABEL: Record<string, string> = {
  facebook_ads: "Facebook Ads",
  meta: "Facebook Ads",
  tiktok_ads: "TikTok Ads",
  tiktok_organic: "TikTok",
};

const MARKET_KEY = "ps.market";
/** Last market viewed — a per-browser convenience only; the server holds the real list. */
export function rememberMarket(code: string) {
  try { localStorage.setItem(MARKET_KEY, code); } catch {}
}
export function recallMarket(): string | null {
  try { return localStorage.getItem(MARKET_KEY); } catch { return null; }
}

/** English name when we have one (1688 titles are Chinese), else the original. */
export function displayTitle(p: { title: string; title_en?: string | null }): string {
  return p.title_en?.trim() || p.title;
}

/** The original title, when it differs from what displayTitle shows. */
export function originalTitle(p: { title: string; title_en?: string | null }): string | null {
  return p.title_en?.trim() && p.title_en.trim() !== p.title ? p.title : null;
}

/** "just now", "5m ago", "3h ago", "2d ago". */
export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "never";
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

/** 7900 -> "7.9k", 1250000 -> "1.3M". */
export function compactCount(n: number): string {
  return new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(n);
}
