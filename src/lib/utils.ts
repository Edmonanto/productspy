import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Daily Winners colours: 70+ is a winner, 60-69 rising. */
export function scoreColor(score: number): string {
  if (score >= 70) return "text-emerald-400";
  if (score >= 60) return "text-amber-400";
  return "text-zinc-400";
}

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

/** Daily Winners score pillars and their maximum points (backend: winners/scoring.py). */
export const PILLAR_MAX = { scaling: 30, engagement: 25, demand: 20, margin: 15, freshness: 10 } as const;

export const PILLAR_LABEL: Record<keyof typeof PILLAR_MAX, string> = {
  scaling: "Scaling proof",
  engagement: "Engagement",
  demand: "Proven demand",
  margin: "Margin",
  freshness: "Freshness",
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
