"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import useSWR, { mutate } from "swr";
import { Check, Globe2, Lock } from "lucide-react";
import { winnersApi } from "@/lib/api";
import { cn, rememberMarket } from "@/lib/utils";

/** Which markets Daily Winners follows. Saved server-side; the plan caps how many. */
export default function MarketSettings() {
  const { data } = useSWR("winner-markets", winnersApi.markets);
  const [selected, setSelected] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    if (data) setSelected(data.following);
  }, [data]);

  const max = data?.entitlements.markets ?? 1;
  const dirty = !!data && JSON.stringify(selected) !== JSON.stringify(data.following);

  const toggle = (code: string) => {
    setMsg(null);
    if (selected.includes(code)) setSelected(selected.filter((c) => c !== code));
    else if (max === 1) setSelected([code]); // single-market plans just switch
    else if (selected.length < max) setSelected([...selected, code]);
    else setMsg({ ok: false, text: `Your plan includes ${max} markets — remove one first, or upgrade.` });
  };

  const save = async () => {
    setSaving(true);
    setMsg(null);
    try {
      const res = await winnersApi.setMarkets(selected);
      rememberMarket(res.markets[0]);
      await mutate("winner-markets");
      setMsg({ ok: true, text: "Saved. Daily Winners now follows these markets." });
    } catch (e) {
      setMsg({ ok: false, text: (e as Error).message });
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-4">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h2 className="text-white font-semibold text-sm flex items-center gap-2"><Globe2 size={15} /> Target markets</h2>
          <p className="text-zinc-500 text-xs mt-1">
            Daily Winners are picked per country, from ads and videos shown there. Your plan includes{" "}
            <span className="text-zinc-300">{max >= 99 ? "every" : max} market{max === 1 ? "" : "s"}</span>.
          </p>
        </div>
        {max < 99 && (
          <Link href="/dashboard/billing" className="inline-flex items-center py-3 -my-3 text-xs text-violet-400 hover:text-violet-300">More markets →</Link>
        )}
      </div>

      {!data ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 animate-pulse">
          {Array.from({ length: 6 }).map((_, i) => <div key={i} className="h-14 bg-zinc-800 rounded-lg" />)}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
          {data.markets.map((m) => {
            const on = selected.includes(m.code);
            const full = !on && max > 1 && selected.length >= max;
            return (
              <button
                key={m.code}
                onClick={() => toggle(m.code)}
                className={cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-lg border text-left transition-colors",
                  on ? "bg-violet-600/15 border-violet-500/40" : "bg-zinc-950 border-zinc-800 hover:border-zinc-700",
                  full && "opacity-50"
                )}
              >
                <span className="text-lg leading-none">{m.flag}</span>
                <span className="flex-1 min-w-0">
                  <span className="block text-sm text-white truncate">{m.name}</span>
                  <span className="block text-[11px] text-zinc-500">{m.currency}</span>
                </span>
                {on ? <Check size={15} className="text-violet-300" /> : full ? <Lock size={13} className="text-zinc-500" /> : null}
              </button>
            );
          })}
        </div>
      )}

      <div className="flex items-center gap-3 flex-wrap">
        <button
          onClick={save}
          disabled={!dirty || saving || selected.length === 0}
          className="px-4 py-2 max-md:min-h-[44px] rounded-lg bg-violet-600 text-white text-sm font-medium hover:bg-violet-500 disabled:opacity-40"
        >
          {saving ? "Saving…" : "Save markets"}
        </button>
        {msg && <span className={cn("text-sm", msg.ok ? "text-emerald-400" : "text-amber-300")}>{msg.text}</span>}
      </div>
    </section>
  );
}
