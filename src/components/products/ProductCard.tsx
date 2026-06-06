"use client";

import Link from "next/link";
import { Bookmark, ExternalLink } from "lucide-react";
import { Product, watchlistApi } from "@/lib/api";
import { formatPrice, estimatedMargin, sourceIcon } from "@/lib/utils";
import ScoreBadge from "./ScoreBadge";
import { useState } from "react";

interface Props {
  product: Product;
  inWatchlist?: boolean;
}

export default function ProductCard({ product, inWatchlist = false }: Props) {
  const [saved, setSaved] = useState(inWatchlist);
  const [loading, setLoading] = useState(false);

  const toggleWatchlist = async (e: React.MouseEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      if (saved) {
        await watchlistApi.remove(product.id);
      } else {
        await watchlistApi.add(product.id);
      }
      setSaved(!saved);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const score = product.score?.overall_score ?? 0;
  const margin = estimatedMargin(product.price_usd, product.cost_usd);

  return (
    <Link href={`/dashboard/products/${product.id}`}>
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden hover:border-zinc-600 transition-all hover:shadow-lg hover:shadow-black/30 group cursor-pointer">
        {/* Image */}
        <div className="relative aspect-square bg-zinc-800 overflow-hidden">
          {product.image_url ? (
            <img
              src={product.image_url}
              alt={product.title}
              className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-4xl">
              {sourceIcon(product.source)}
            </div>
          )}

          {/* Score badge overlay */}
          <div className="absolute top-2 left-2">
            <ScoreBadge score={score} />
          </div>

          {/* Watchlist button */}
          <button
            onClick={toggleWatchlist}
            disabled={loading}
            className={`absolute top-2 right-2 p-1.5 rounded-lg backdrop-blur-sm transition-colors
              ${saved
                ? "bg-violet-600 text-white"
                : "bg-zinc-900/70 text-zinc-400 hover:text-white hover:bg-zinc-800"
              }`}
          >
            <Bookmark size={14} fill={saved ? "currentColor" : "none"} />
          </button>

          {/* Source tag */}
          <div className="absolute bottom-2 right-2 text-xs bg-zinc-900/80 backdrop-blur-sm text-zinc-400 px-2 py-0.5 rounded-full">
            {sourceIcon(product.source)} {product.source}
          </div>
        </div>

        {/* Info */}
        <div className="p-3 space-y-2">
          <p className="text-zinc-200 text-sm font-medium leading-snug line-clamp-2">
            {product.title}
          </p>

          <div className="flex items-center justify-between text-xs">
            <div className="space-y-0.5">
              <div className="text-zinc-500">Price</div>
              <div className="text-white font-semibold">{formatPrice(product.price_usd)}</div>
            </div>
            <div className="space-y-0.5 text-right">
              <div className="text-zinc-500">Est. Margin</div>
              <div className={`font-semibold ${margin === "N/A" ? "text-zinc-500" : "text-emerald-400"}`}>
                {margin}
              </div>
            </div>
            <div className="space-y-0.5 text-right">
              <div className="text-zinc-500">Cost</div>
              <div className="text-zinc-300">{formatPrice(product.cost_usd)}</div>
            </div>
          </div>

          {product.score?.ai_summary && (
            <p className="text-zinc-500 text-xs line-clamp-2 border-t border-zinc-800 pt-2">
              {product.score.ai_summary}
            </p>
          )}
        </div>
      </div>
    </Link>
  );
}
