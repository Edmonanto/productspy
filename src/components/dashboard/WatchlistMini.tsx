"use client";

import Link from "next/link";
import { WatchlistItem } from "@/lib/api";
import { scoreColor } from "@/lib/utils";
import { Bookmark, ArrowRight, ImageOff } from "lucide-react";
import ProductImage from "@/components/products/ProductImage";

interface Props {
  items: WatchlistItem[];
  loading?: boolean;
}

export default function WatchlistMini({ items, loading }: Props) {
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-white font-semibold text-sm flex items-center gap-2">
          <Bookmark size={13} className="text-violet-400" />
          Watchlist
        </h3>
        <Link
          href="/dashboard/watchlist"
          className="flex items-center gap-1 text-violet-400 hover:text-violet-300 text-xs transition-colors"
        >
          View all <ArrowRight size={11} />
        </Link>
      </div>

      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="flex items-center gap-3 animate-pulse">
              <div className="w-9 h-9 bg-zinc-800 rounded-lg" />
              <div className="flex-1 space-y-1.5">
                <div className="h-3 bg-zinc-800 rounded w-2/3" />
                <div className="h-2 bg-zinc-800 rounded w-1/3" />
              </div>
            </div>
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center py-8 text-center">
          <Bookmark size={28} className="text-zinc-700 mb-2" />
          <p className="text-zinc-600 text-xs">Nothing saved yet</p>
          <Link href="/dashboard/winners" className="text-violet-400 text-xs mt-1 hover:text-violet-300">
            Browse Daily Winners →
          </Link>
        </div>
      ) : (
        <div className="space-y-2">
          {items.slice(0, 5).map(({ product, added_at }) => {
            const score = product.score;
            return (
              <Link key={product.id} href={`/dashboard/winners/${product.id}${product.market ? `?market=${product.market}` : ""}`}>
                <div className="flex items-center gap-3 p-2 rounded-lg hover:bg-zinc-800 transition-colors group">
                  <div className="w-9 h-9 rounded-lg bg-zinc-800 overflow-hidden shrink-0">
                    <ProductImage
                      src={product.image_url}
                      alt={product.title}
                      className="w-full h-full object-cover"
                      fallback={
                        <div className="w-full h-full flex items-center justify-center text-zinc-600">
                          <ImageOff size={14} />
                        </div>
                      }
                    />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-zinc-200 text-xs font-medium truncate group-hover:text-white">
                      {product.title}
                    </p>
                    <p className="text-zinc-600 text-[10px]">
                      Saved {new Date(added_at).toLocaleDateString()}
                    </p>
                  </div>
                  {score != null && (
                    <span className={`text-sm font-extrabold shrink-0 ${scoreColor(score)}`}>{score}</span>
                  )}
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
