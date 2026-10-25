"use client";

import Link from "next/link";
import { Settings2 } from "lucide-react";
import { Market } from "@/lib/api";
import { cn } from "@/lib/utils";

interface Props {
  markets: Market[];
  following: string[];
  value: string;
  onChange: (code: string) => void;
}

/** Pills for the markets the user follows + a link to change them in Settings. */
export default function MarketPicker({ markets, following, value, onChange }: Props) {
  const byCode = Object.fromEntries(markets.map((m) => [m.code, m]));
  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      {following.map((code) => {
        const m = byCode[code];
        if (!m) return null;
        return (
          <button
            key={code}
            onClick={() => onChange(code)}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors",
              value === code
                ? "bg-violet-600/20 text-violet-200 border-violet-500/40"
                : "bg-zinc-900 text-zinc-400 border-zinc-800 hover:text-white hover:border-zinc-700"
            )}
          >
            <span className="text-sm leading-none">{m.flag}</span>
            {m.name}
          </button>
        );
      })}
      <Link
        href="/dashboard/settings"
        className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs text-zinc-500 hover:text-white hover:bg-zinc-800 transition-colors"
      >
        <Settings2 size={13} />
        Change markets
      </Link>
    </div>
  );
}
