"use client";

import Link from "next/link";
import { Zap, ArrowRight } from "lucide-react";
import { Me } from "@/lib/api";
import { cn } from "@/lib/utils";

interface Props {
  me: Me | undefined;
}

const PLAN_COLORS: Record<string, string> = {
  free:    "bg-zinc-700 text-zinc-300",
  starter: "bg-blue-600/20 text-blue-400 border border-blue-600/30",
  pro:     "bg-violet-600/20 text-violet-400 border border-violet-600/30",
  agency:  "bg-amber-600/20 text-amber-400 border border-amber-600/30",
};

export default function QuotaWidget({ me }: Props) {
  const plan = me?.subscription.plan ?? "free";
  const quota = me?.quota;
  const isUnlimited = quota?.limit === "unlimited";
  const used = Number(quota?.used ?? 0);
  const limit = Number(quota?.limit ?? 5);
  const pct = isUnlimited ? 0 : Math.min(100, Math.round((used / limit) * 100));
  const remaining = isUnlimited ? "∞" : quota?.remaining ?? 0;
  const nearLimit = !isUnlimited && pct >= 80;

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Zap size={14} className="text-violet-400" />
          <span className="text-zinc-400 text-sm font-medium">Daily searches</span>
        </div>
        <span className={cn("text-xs font-bold px-2.5 py-1 rounded-full capitalize", PLAN_COLORS[plan])}>
          {plan}
        </span>
      </div>

      {/* Usage numbers */}
      <div className="flex items-end justify-between">
        <div>
          <span className={cn("text-3xl font-extrabold", nearLimit ? "text-red-400" : "text-white")}>
            {used}
          </span>
          <span className="text-zinc-600 text-lg font-bold">
            /{isUnlimited ? "∞" : limit}
          </span>
        </div>
        <div className="text-right">
          <p className="text-zinc-500 text-xs">Remaining</p>
          <p className={cn("text-lg font-bold", nearLimit ? "text-red-400" : "text-emerald-400")}>
            {remaining}
          </p>
        </div>
      </div>

      {/* Progress bar */}
      {!isUnlimited && (
        <div className="space-y-1.5">
          <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
            <div
              className={cn(
                "h-full rounded-full transition-all duration-500",
                pct >= 80 ? "bg-red-500" : pct >= 50 ? "bg-yellow-500" : "bg-violet-500"
              )}
              style={{ width: `${pct}%` }}
            />
          </div>
          <p className="text-zinc-600 text-xs">Resets at midnight UTC</p>
        </div>
      )}

      {/* Upgrade CTA — only for free/starter */}
      {plan === "free" && (
        <Link
          href="/dashboard/billing"
          className="flex items-center justify-between w-full bg-violet-600/10 hover:bg-violet-600/20 border border-violet-600/20 text-violet-400 text-xs font-medium px-3 py-2.5 rounded-lg transition-colors"
        >
          <span>Upgrade for unlimited searches</span>
          <ArrowRight size={12} />
        </Link>
      )}
      {plan === "starter" && (
        <Link
          href="/dashboard/billing"
          className="flex items-center justify-between w-full bg-violet-600/10 hover:bg-violet-600/20 border border-violet-600/20 text-violet-400 text-xs font-medium px-3 py-2.5 rounded-lg transition-colors"
        >
          <span>Upgrade to Pro for unlimited</span>
          <ArrowRight size={12} />
        </Link>
      )}
    </div>
  );
}
