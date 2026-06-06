"use client";

import useSWR from "swr";
import { watchlistApi, WatchlistItem } from "@/lib/api";
import ProductCard from "@/components/products/ProductCard";
import Topbar from "@/components/layout/Topbar";
import { Bookmark } from "lucide-react";

export default function WatchlistPage() {
  const { data, isLoading } = useSWR("watchlist", () => watchlistApi.list());
  const items: WatchlistItem[] = data?.items ?? [];

  return (
    <div className="flex flex-col h-full">
      <Topbar title="My Watchlist" />

      <div className="p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center gap-3">
          <Bookmark size={16} className="text-violet-400" />
          <span className="text-zinc-400 text-sm">
            <span className="text-white font-bold">{items.length}</span> saved products
          </span>
        </div>

        {isLoading ? (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
            {Array.from({ length: 10 }).map((_, i) => (
              <div key={i} className="bg-zinc-900 border border-zinc-800 rounded-xl aspect-[3/4] animate-pulse" />
            ))}
          </div>
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-32 text-center">
            <Bookmark size={40} className="text-zinc-700 mb-4" />
            <p className="text-zinc-400 font-medium">No saved products yet</p>
            <p className="text-zinc-600 text-sm mt-1">
              Browse trending products and click the bookmark icon to save them here
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
            {items.map(({ product }) => (
              <ProductCard key={product.id} product={product} inWatchlist />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
