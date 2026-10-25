"use client";

import Link from "next/link";
import useSWR from "swr";
import { Clock, Sparkles } from "lucide-react";
import { usersApi, Me } from "@/lib/api";
import { cn } from "@/lib/utils";

/** Thin bar on every dashboard page: trial countdown, or upsell after it ends. */
export default function TrialBanner() {
  const { data: me } = useSWR<Me>("me", usersApi.me);
  const t = me?.trial;
  if (!t) return null;

  if (t.active) {
    const urgent = t.days_left <= 2;
    const left = t.days_left <= 1 ? `${Math.max(1, t.hours_left)} hours` : `${t.days_left} days`;
    return (
      <div className={cn(
        "flex items-center justify-center gap-2 px-4 py-2 text-xs border-b flex-wrap",
        urgent ? "bg-amber-500/10 border-amber-500/20 text-amber-200" : "bg-violet-600/10 border-violet-500/20 text-violet-200"
      )}>
        <Clock size={13} />
        <span>
          <b>{left}</b> left in your free Pro trial.
          <span className="hidden sm:inline"> Keep all daily winners after it ends.</span>
        </span>
        <Link href="/dashboard/billing" className="inline-flex items-center py-3 -my-3 ml-1 font-semibold underline underline-offset-2 hover:text-white">
          Choose a plan
        </Link>
      </div>
    );
  }

  if (t.eligible) {
    return (
      <div className="flex items-center justify-center gap-2 px-4 py-2 text-xs border-b flex-wrap bg-violet-600/10 border-violet-500/20 text-violet-200">
        <Sparkles size={13} />
        <span>Try Pro free for {t.length_days} days — no card needed.</span>
        <Link href="/dashboard/billing" className="inline-flex items-center py-3 -my-3 font-semibold underline underline-offset-2 hover:text-white">Start trial</Link>
      </div>
    );
  }

  if (t.expired && me?.subscription.plan === "free") {
    return (
      <div className="flex items-center justify-center gap-2 px-4 py-2 text-xs border-b flex-wrap bg-zinc-900 border-zinc-800 text-zinc-300">
        <span>Your trial ended — you now see the top 3 winners a day.</span>
        <Link href="/dashboard/billing" className="inline-flex items-center py-3 -my-3 font-semibold text-violet-300 hover:text-violet-200">Unlock all winners →</Link>
      </div>
    );
  }
  return null;
}
