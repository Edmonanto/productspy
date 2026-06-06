import { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  label: string;
  value: string | number;
  sub?: string;
  icon: LucideIcon;
  trend?: "up" | "down" | "neutral";
  trendValue?: string;
  accent?: "violet" | "emerald" | "yellow" | "blue";
}

const ACCENTS = {
  violet: "bg-violet-600/20 text-violet-400",
  emerald: "bg-emerald-600/20 text-emerald-400",
  yellow:  "bg-yellow-600/20 text-yellow-400",
  blue:    "bg-blue-600/20 text-blue-400",
};

const TREND_COLORS = {
  up:      "text-emerald-400",
  down:    "text-red-400",
  neutral: "text-zinc-500",
};

const TREND_ICONS = { up: "↑", down: "↓", neutral: "→" };

export default function StatCard({ label, value, sub, icon: Icon, trend, trendValue, accent = "violet" }: Props) {
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-zinc-500 text-xs font-medium">{label}</span>
        <div className={cn("w-8 h-8 rounded-lg flex items-center justify-center", ACCENTS[accent])}>
          <Icon size={14} />
        </div>
      </div>
      <div>
        <div className="text-2xl font-extrabold text-white">{value}</div>
        {sub && <p className="text-zinc-600 text-xs mt-0.5">{sub}</p>}
      </div>
      {trend && trendValue && (
        <div className={cn("flex items-center gap-1 text-xs font-medium", TREND_COLORS[trend])}>
          <span>{TREND_ICONS[trend]}</span>
          <span>{trendValue}</span>
        </div>
      )}
    </div>
  );
}
