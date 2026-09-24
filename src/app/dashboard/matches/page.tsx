"use client";

import { useState } from "react";
import useSWR from "swr";
import {
  GitCompareArrows, Check, X, ExternalLink, AlertTriangle, Loader2,
} from "lucide-react";
import Topbar from "@/components/layout/Topbar";
import { matchesApi, ProductMatch } from "@/lib/api";
import { cn } from "@/lib/utils";
import ProductImage from "@/components/products/ProductImage";

const TABS = [
  { key: "candidate", label: "Needs review" },
  { key: "confirmed", label: "Confirmed" },
  { key: "rejected", label: "Rejected" },
] as const;

function money(n: number | null | undefined) {
  return n == null ? "—" : `$${n.toFixed(2)}`;
}

/** Confidence is capped at 0.75 in v1, so the bar is scaled to that ceiling
 *  rather than to 1.0 — otherwise every match looks weak. */
function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.min(100, Math.round((value / 0.75) * 100));
  const tone =
    pct >= 85 ? "bg-emerald-500" : pct >= 60 ? "bg-amber-500" : "bg-zinc-500";
  return (
    <div className="flex items-center gap-2">
      <div className="w-20 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
        <div className={cn("h-full rounded-full", tone)} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-zinc-400 font-mono">{value.toFixed(2)}</span>
    </div>
  );
}

function Side({
  label, title, subtitle, image, url, primary, secondary, tone,
}: {
  label: string; title: string; subtitle?: string | null;
  image: string | null; url: string;
  primary: string; secondary?: string | null; tone: string;
}) {
  return (
    <div className="flex-1 min-w-0 flex gap-3">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <ProductImage
        src={image}
        alt=""
        className="w-16 h-16 rounded-lg object-cover bg-zinc-800 shrink-0"
        fallback={<div className="w-16 h-16 rounded-lg bg-zinc-800 shrink-0" />}
      />
      <div className="min-w-0">
        <span className={cn("text-[10px] font-semibold uppercase tracking-wide", tone)}>
          {label}
        </span>
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="block text-sm text-white hover:text-violet-400 line-clamp-2 leading-snug"
        >
          {title}
          <ExternalLink size={11} className="inline ml-1 mb-0.5 opacity-50" />
        </a>
        {subtitle && (
          <p className="text-xs text-zinc-500 line-clamp-1 mt-0.5">{subtitle}</p>
        )}
        <p className="text-sm font-bold text-white mt-1">
          {primary}
          {secondary && <span className="text-zinc-500 font-normal ml-2">{secondary}</span>}
        </p>
      </div>
    </div>
  );
}

function MatchRow({ match, onDone }: { match: ProductMatch; onDone: () => void }) {
  const [busy, setBusy] = useState<"confirm" | "reject" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const shared = match.evidence.distinctive_tokens ?? match.evidence.shared_tokens ?? [];

  async function act(kind: "confirm" | "reject") {
    setBusy(kind);
    setError(null);
    try {
      if (kind === "confirm") await matchesApi.confirm(match.id);
      else await matchesApi.reject(match.id);
      onDone();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
      setBusy(null);
    }
  }

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-3">
      <div className="flex flex-col lg:flex-row gap-4 lg:items-start">
        <Side
          label={match.retail.source}
          title={match.retail.title}
          image={match.retail.image_url}
          url={match.retail.product_url}
          primary={money(match.retail.price_usd)}
          secondary={
            match.retail.orders_count != null
              ? `${match.retail.orders_count.toLocaleString()} sold`
              : null
          }
          tone="text-sky-400"
        />

        <div className="hidden lg:flex flex-col items-center justify-center px-2 shrink-0">
          <GitCompareArrows size={16} className="text-zinc-600" />
        </div>

        <Side
          label={match.supplier.source}
          title={match.supplier.title_en || match.supplier.title}
          subtitle={match.supplier.title_en ? match.supplier.title : null}
          image={match.supplier.image_url}
          url={match.supplier.product_url}
          primary={money(match.supplier.cost_usd)}
          secondary="cost"
          tone="text-orange-400"
        />
      </div>

      {/* Evidence — why the matcher paired these */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs border-t border-zinc-800 pt-3">
        <ConfidenceBar value={match.confidence} />

        {shared.length > 0 && (
          <div className="flex flex-wrap gap-1 items-center">
            <span className="text-zinc-600">matched on</span>
            {shared.slice(0, 6).map((t) => (
              <span key={t} className="px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-300 font-mono text-[10px]">
                {t}
              </span>
            ))}
          </div>
        )}

        {match.evidence.price_ratio != null && (
          <span className="text-zinc-500">{match.evidence.price_ratio}× markup</span>
        )}

        {match.evidence.generic_only && (
          <span className="flex items-center gap-1 text-amber-500">
            <AlertTriangle size={11} />
            only generic words in common
          </span>
        )}

        {match.projected_margin_pct != null && (
          <span className="ml-auto text-zinc-400">
            margin if confirmed{" "}
            <span className="text-emerald-400 font-bold">
              {match.projected_margin_pct}%
            </span>
          </span>
        )}
      </div>

      {error && <p className="text-xs text-red-400">{error}</p>}

      {match.status === "candidate" && (
        <div className="flex gap-2">
          <button
            onClick={() => act("confirm")}
            disabled={busy !== null}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-semibold transition-colors"
          >
            {busy === "confirm" ? <Loader2 size={13} className="animate-spin" /> : <Check size={13} />}
            Same product — apply cost
          </button>
          <button
            onClick={() => act("reject")}
            disabled={busy !== null}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-red-900/40 hover:text-red-400 disabled:opacity-50 text-zinc-400 text-xs font-semibold transition-colors"
          >
            {busy === "reject" ? <Loader2 size={13} className="animate-spin" /> : <X size={13} />}
            Not a match
          </button>
        </div>
      )}
    </div>
  );
}

export default function MatchesPage() {
  const [tab, setTab] = useState<(typeof TABS)[number]["key"]>("candidate");
  const { data, isLoading, mutate } = useSWR(["matches", tab], () =>
    matchesApi.list(tab)
  );

  const items = data?.items ?? [];
  const counts = data?.counts ?? {};

  return (
    <div className="flex flex-col h-full">
      <Topbar title="Match review" />

      <div className="p-6 space-y-5">
        <p className="text-sm text-zinc-400 max-w-2xl">
          Each pair links a listing you can sell against to a supplier you can buy
          from. Confirming applies the supplier&apos;s real cost, replacing an
          estimated margin with an observed one —{" "}
          <span className="text-zinc-300">nothing changes until you confirm.</span>
        </p>

        <div className="flex gap-2">
          {TABS.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={cn(
                "px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors",
                tab === key
                  ? "bg-violet-600/20 text-violet-400 border border-violet-600/30"
                  : "bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-white"
              )}
            >
              {label}
              {counts[key] != null && (
                <span className="ml-1.5 text-zinc-500">{counts[key]}</span>
              )}
            </button>
          ))}
        </div>

        {isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="bg-zinc-900 border border-zinc-800 rounded-xl h-32 animate-pulse" />
            ))}
          </div>
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-28 text-center">
            <GitCompareArrows size={40} className="text-zinc-700 mb-4" />
            <p className="text-zinc-400 font-medium">
              {tab === "candidate" ? "Nothing to review" : `No ${tab} matches`}
            </p>
            <p className="text-zinc-600 text-sm mt-1 max-w-sm">
              {tab === "candidate"
                ? "Matches appear here after an ingestion run finds a supplier that may sell the same product."
                : "Reviewed matches will be listed here."}
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {items.map((m) => (
              <MatchRow key={m.id} match={m} onDone={() => mutate()} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
