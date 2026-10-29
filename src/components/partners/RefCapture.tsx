"use client";

import { useEffect, useState } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import { Gift, X } from "lucide-react";
import { partnersApi } from "@/lib/api";

/** Partner link capture: ?ref=CODE is remembered for 30 days (this browser only)
 *  and attached to the account at signup. The server decides if it counts. */
const KEY = "ps.ref";
const TTL = 30 * 24 * 3600 * 1000;

export interface StoredRef { code: string; partner: string; discount: number; at: number; sent?: boolean }

export function readRef(): StoredRef | null {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) || "null");
    if (!v || typeof v.code !== "string" || Date.now() - v.at > TTL) return null;
    return v;
  } catch { return null; }
}

export function writeRef(v: StoredRef | null) {
  try { v ? localStorage.setItem(KEY, JSON.stringify(v)) : localStorage.removeItem(KEY); } catch {}
}

/** Mounted in the root layout: captures ?ref and shows the discount on public pages. */
export default function RefCapture() {
  const params = useSearchParams();
  const pathname = usePathname();
  const [ref, setRef] = useState<StoredRef | null>(null);
  const [hidden, setHidden] = useState(false);

  useEffect(() => {
    const code = params.get("ref");
    const existing = readRef();
    if (code && (!existing || existing.code.toUpperCase() !== code.toUpperCase()) && !existing?.sent) {
      partnersApi.offer(code).then((o) => {
        if (!o.valid || !o.code) return;
        const v = { code: o.code, partner: o.partner ?? "", discount: o.discount_pct ?? 0, at: Date.now() };
        // First touch wins: an earlier, still-valid link is kept.
        if (!existing) { writeRef(v); setRef(v); }
        partnersApi.click(o.code).catch(() => {});
      }).catch(() => {});
    } else {
      setRef(existing);
    }
  }, [params]);

  if (!ref || hidden || pathname.startsWith("/dashboard") || !ref.discount) return null;
  return (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 w-[calc(100%-2rem)] max-w-md flex items-center gap-3 bg-violet-600 text-white rounded-xl shadow-xl shadow-black/40 px-4 py-3">
      <Gift size={20} className="shrink-0" />
      <p className="text-sm flex-1">
        <b>{ref.discount}% off your first month</b>{ref.partner ? <> — invited by {ref.partner}</> : null}. Applied automatically when you subscribe.
      </p>
      <button onClick={() => setHidden(true)} aria-label="Hide" className="p-1.5 rounded-lg hover:bg-white/15"><X size={16} /></button>
    </div>
  );
}
