"use client";

import Link from "next/link";
import { Columns3, X } from "lucide-react";
import { useCompare } from "@/lib/compare";

/** Floating bar once two or more products are picked for comparison. */
export default function CompareTray({ market }: { market: string | null }) {
  const { ids, clear } = useCompare();
  if (ids.length < 1) return null;
  return (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-40 flex items-center gap-2 bg-zinc-900 border border-zinc-700 shadow-xl shadow-black/40 rounded-full pl-4 pr-1.5 py-1.5 whitespace-nowrap print:hidden">
      <Columns3 size={14} className="text-violet-300" />
      <span className="text-sm text-zinc-200">{ids.length} selected</span>
      <Link href={`/dashboard/compare${market ? `?market=${market}` : ""}`}
            className={`text-sm font-medium rounded-full px-3 py-1.5 ${ids.length >= 2 ? "bg-violet-600 hover:bg-violet-500 text-white" : "bg-zinc-800 text-zinc-400 pointer-events-none"}`}
            aria-disabled={ids.length < 2}>
        Compare{ids.length < 2 ? " (pick 2+)" : ""}
      </Link>
      <button onClick={clear} aria-label="Clear comparison" className="p-2 rounded-full text-zinc-400 hover:text-white hover:bg-zinc-800">
        <X size={14} />
      </button>
    </div>
  );
}
