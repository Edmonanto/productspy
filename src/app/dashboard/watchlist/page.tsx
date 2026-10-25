"use client";

import Link from "next/link";
import useSWR from "swr";
import { Bookmark, ImageOff, Trash2 } from "lucide-react";
import Topbar from "@/components/layout/Topbar";
import ProductImage from "@/components/products/ProductImage";
import ScoreRing from "@/components/winners/ScoreRing";
import { watchlistApi, WatchlistItem } from "@/lib/api";
import { formatPrice } from "@/lib/utils";

export default function WatchlistPage() {
  const { data, isLoading, mutate } = useSWR("watchlist", () => watchlistApi.list());
  const items: WatchlistItem[] = data?.items ?? [];

  const remove = async (productId: string) => {
    await watchlistApi.remove(productId);
    await mutate();
  };

  return (
    <div className="flex flex-col h-full">
      <Topbar title="My Watchlist" />

      <div className="p-4 sm:p-6 space-y-6 max-w-6xl w-full mx-auto">
        <div className="flex items-center gap-3">
          <Bookmark size={16} className="text-violet-400" />
          <span className="text-zinc-400 text-sm">
            <span className="text-white font-bold">{items.length}</span> saved products
          </span>
        </div>

        {isLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="bg-zinc-900 border border-zinc-800 rounded-xl h-28 animate-pulse" />
            ))}
          </div>
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-32 text-center">
            <Bookmark size={40} className="text-zinc-700 mb-4" />
            <p className="text-zinc-400 font-medium">No saved products yet</p>
            <p className="text-zinc-600 text-sm mt-1">
              Open <Link href="/dashboard/winners" className="text-violet-400 hover:text-violet-300">Daily Winners</Link>{" "}
              and press Save on a product to keep it here.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {items.map(({ product: p, added_at }) => {
              const markup = p.price_usd && p.cost_usd ? p.price_usd / p.cost_usd : null;
              const href = `/dashboard/winners/${p.id}${p.market ? `?market=${p.market}` : ""}`;
              return (
                <div key={p.id} className="bg-zinc-900 border border-zinc-800 rounded-xl p-3 flex gap-3 hover:border-zinc-700 transition-colors">
                  <Link href={href} className="w-20 h-20 rounded-lg bg-zinc-800 overflow-hidden shrink-0">
                    <ProductImage
                      src={p.image_url}
                      alt={p.title}
                      className="w-full h-full object-cover"
                      fallback={<div className="w-full h-full flex items-center justify-center text-zinc-600"><ImageOff size={18} /></div>}
                    />
                  </Link>
                  <div className="flex-1 min-w-0 space-y-1">
                    <Link href={href} className="block text-sm text-zinc-200 font-medium leading-snug line-clamp-2 hover:text-white">
                      {p.title}
                    </Link>
                    <div className="text-xs text-zinc-500">
                      {formatPrice(p.price_usd)}
                      {markup && <span className="text-emerald-400"> · {markup.toFixed(1)}× cost</span>}
                    </div>
                    <div className="flex items-center justify-between text-[11px] text-zinc-600">
                      <span>{p.market ? `${p.market} · ` : ""}saved {new Date(added_at).toLocaleDateString()}</span>
                      <button onClick={() => remove(p.id)} className="p-1 text-zinc-600 hover:text-red-400" aria-label="Remove">
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </div>
                  {p.score != null ? (
                    <ScoreRing score={p.score} size={44} stroke={4} />
                  ) : (
                    <span className="text-[10px] text-zinc-600 self-start mt-1 w-11 text-center leading-tight">not picked this week</span>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
