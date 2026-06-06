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
  };
  return map[source] || "🌐";
}
