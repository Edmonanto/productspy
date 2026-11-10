"use client";

import { useState } from "react";
import Link from "next/link";
import useSWR, { mutate } from "swr";
import { Loader2, Lock, Settings2 } from "lucide-react";
import { Market, winnersApi } from "@/lib/api";
import { cn, rememberMarket } from "@/lib/utils";

interface Props {
  markets: Market[];
  following: string[];
  value: string;
  onChange: (code: string) => void;
}

/**
 * Every live market as a one-click pill. Markets the user already follows open
 * straight away; any other market is followed on the spot (single-market plans
 * just switch; full multi-market plans swap out the market being viewed), so
 * nobody has to go through Settings to look at another country.
 */
export default function MarketPicker({ markets, following, value, onChange }: Props) {
  const meta = useSWR("winner-markets", winnersApi.markets);
  const saved = meta.data?.following ?? following;
  const max = meta.data?.entitlements.markets ?? Math.max(1, saved.length);
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const byCode = Object.fromEntries(markets.map((m) => [m.code, m]));
  // Followed markets first, then the rest in the server's order.
  const ordered = [
    ...following.filter((c) => byCode[c]),
    ...markets.map((m) => m.code).filter((c) => !following.includes(c)),
  ];

  const pick = async (code: string) => {
    setMsg(null);
    if (code === value) return;
    if (saved.includes(code)) {
      onChange(code);
      return;
    }
    // Not followed yet: add it if the plan has room, otherwise replace.
    let next: string[];
    let replaced: string | null = null;
    if (saved.length < max) next = [...saved, code];
    else if (max === 1) {
      replaced = saved[0] ?? null;
      next = [code];
    } else {
      replaced = saved.includes(value) ? value : saved[saved.length - 1];
      next = saved.map((c) => (c === replaced ? code : c));
    }
    setBusy(code);
    try {
      await winnersApi.setMarkets(next);
      rememberMarket(code);
      await mutate("winner-markets");
      onChange(code);
      if (replaced && byCode[replaced]) {
        setMsg({
          ok: true,
          text: `Switched to ${byCode[code]?.name ?? code}. Your plan includes ${max} market${max === 1 ? "" : "s"}, so ${byCode[replaced].name} was swapped out — switch back any time.`,
        });
      }
    } catch (e) {
      setMsg({ ok: false, text: (e as Error).message });
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-1.5 flex-wrap" role="tablist" aria-label="Market">
        {ordered.map((code) => {
          const m = byCode[code];
          const active = value === code;
          const followed = saved.includes(code);
          return (
            <button
              key={code}
              role="tab"
              aria-selected={active}
              disabled={!!busy}
              onClick={() => pick(code)}
              title={followed ? m.name : `Switch to ${m.name}`}
              className={cn(
                "flex items-center gap-1.5 px-3 py-1.5 max-md:min-h-[44px] rounded-lg text-xs font-medium border transition-colors disabled:cursor-wait",
                active
                  ? "bg-violet-600/20 text-violet-200 border-violet-500/40"
                  : followed
                    ? "bg-zinc-900 text-zinc-300 border-zinc-800 hover:text-white hover:border-zinc-700"
                    : "bg-transparent text-zinc-500 border-dashed border-zinc-800 hover:text-white hover:border-zinc-600"
              )}
            >
              {busy === code ? <Loader2 size={13} className="animate-spin" /> : <span className="text-sm leading-none">{m.flag}</span>}
              {m.name}
            </button>
          );
        })}
        <Link
          href="/dashboard/settings"
          title="Choose markets"
          className="max-md:min-h-[44px] flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs text-zinc-500 hover:text-white hover:bg-zinc-800 transition-colors"
        >
          <Settings2 size={13} />
          <span className="sr-only sm:not-sr-only">Settings</span>
        </Link>
      </div>
      {msg && (
        <p className={cn("text-xs flex items-center gap-1.5", msg.ok ? "text-zinc-400" : "text-amber-300")}>
          {!msg.ok && <Lock size={12} />}
          {msg.text}
          {!msg.ok && <Link href="/dashboard/billing" className="underline ml-1">See plans</Link>}
        </p>
      )}
    </div>
  );
}
