"use client";

import { useState } from "react";
import useSWR from "swr";
import { Mail } from "lucide-react";
import { winnersApi } from "@/lib/api";
import { cn } from "@/lib/utils";

/** On/off switch for the daily winners email. */
export default function EmailSettings() {
  const { data, mutate } = useSWR("winner-digest", winnersApi.digest);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const on = data?.on ?? true;

  const toggle = async () => {
    setSaving(true);
    setError(null);
    try {
      await mutate(winnersApi.setDigest(!on), { revalidate: false });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h2 className="text-white font-semibold text-sm flex items-center gap-2">
            <Mail size={14} /> Daily winners email
          </h2>
          <p id="digest-help" className="text-zinc-500 text-xs mt-1 leading-relaxed">
            Every morning after the scan: the picks for the markets you follow, with a link to each one&apos;s ads
            and evidence.
          </p>
        </div>
        <button
          role="switch"
          aria-checked={on}
          aria-describedby="digest-help"
          aria-label="Daily winners email"
          disabled={!data || saving}
          onClick={toggle}
          className={cn(
            "relative shrink-0 w-12 h-7 rounded-full transition-colors disabled:opacity-50 max-md:my-2",
            on ? "bg-violet-600" : "bg-zinc-700"
          )}
        >
          <span className={cn(
            "absolute top-1 left-1 w-5 h-5 rounded-full bg-white transition-transform",
            on && "translate-x-5"
          )} />
        </button>
      </div>
      {error && <p className="text-red-400 text-xs mt-2">{error}</p>}
    </section>
  );
}
