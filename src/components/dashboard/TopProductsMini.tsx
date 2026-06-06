"use client";

import Link from "next/link";
import { Product } from "@/lib/api";
import { DEMO_PRODUCTS } from "@/lib/demo-products";
import { formatPrice, scoreColor, scoreLabel, sourceIcon } from "@/lib/utils";
import { ArrowRight } from "lucide-react";

interface Props {
  products: Product[];
  loading?: boolean;
}

export default function TopProductsMini({ products, loading }: Props) {
  const isDemo = products.length === 0 && !loading;
  const displayProducts = isDemo ? DEMO_PRODUCTS : products;

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-white font-semibold text-sm">🔥 Top Products Today</h3>
        <Link
          href="/dashboard/trending"
          className="flex items-center gap-1 text-violet-400 hover:text-violet-300 text-xs transition-colors"
        >
          See all <ArrowRight size={11} />
        </Link>
      </div>

      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex items-center gap-3 animate-pulse">
              <div className="w-10 h-10 bg-zinc-800 rounded-lg shrink-0" />
              <div className="flex-1 space-y-1.5">
                <div className="h-3 bg-zinc-800 rounded w-3/4" />
                <div className="h-2.5 bg-zinc-800 rounded w-1/2" />
              </div>
              <div className="h-6 w-12 bg-zinc-800 rounded-full" />
            </div>
          ))}
        </div>
      ) : (
        <>
          {isDemo && (
            <p className="text-[10px] text-violet-400/70 mb-2">✨ Sample data — real products load once scraper runs</p>
          )}
        <div className="space-y-2">
          {displayProducts.slice(0, 7).map((p, i) => {
            const score = p.score?.overall_score ?? 0;
            return (
              <Link key={p.id} href={`/dashboard/products/${p.id}`}>
                <div className="flex items-center gap-3 p-2 rounded-lg hover:bg-zinc-800 transition-colors group cursor-pointer">
                  {/* Rank */}
                  <span className="text-zinc-700 text-xs font-bold w-4 shrink-0">
                    {i + 1}
                  </span>

                  {/* Image */}
                  <div className="w-10 h-10 rounded-lg bg-zinc-800 overflow-hidden shrink-0">
                    {p.image_url ? (
                      <img src={p.image_url} alt={p.title} className="w-full h-full object-cover" />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-lg">
                        {sourceIcon(p.source)}
                      </div>
                    )}
                  </div>

                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <p className="text-zinc-200 text-xs font-medium truncate group-hover:text-white">
                      {p.title}
                    </p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-zinc-600 text-[10px] capitalize">{p.source}</span>
                      {p.price_usd && (
                        <>
                          <span className="text-zinc-700">·</span>
                          <span className="text-zinc-500 text-[10px]">{formatPrice(p.price_usd)}</span>
                        </>
                      )}
                    </div>
                  </div>

                  {/* Score */}
                  <div className="text-right shrink-0">
                    <span className={`text-sm font-extrabold ${scoreColor(score)}`}>{score}</span>
                    <p className="text-[10px] text-zinc-600">{scoreLabel(score)}</p>
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
        </>
      )}
    </div>
  );
}
