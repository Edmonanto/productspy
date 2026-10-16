import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function scoreColor(score: number): string {
  if (score >= 75) return "text-emerald-400";
  if (score >= 55) return "text-yellow-400";
  return "text-red-400";
}

export function scoreBg(score: number): string {
  if (score >= 75) return "bg-emerald-500/20 border-emerald-500/40";
  if (score >= 55) return "bg-yellow-500/20 border-yellow-500/40";
  return "bg-red-500/20 border-red-500/40";
}

export function scoreLabel(score: number): string {
  if (score >= 80) return "🔥 Hot";
  if (score >= 65) return "📈 Rising";
  if (score >= 50) return "⚡ Decent";
  return "❄️ Weak";
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

export function sourceIcon(source: string): string {
  const map: Record<string, string> = {
    aliexpress: "🛒",
    tiktok: "🎵",
    amazon: "📦",
    "1688": "🏭",
  };
  return map[source] || "🌐";
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
