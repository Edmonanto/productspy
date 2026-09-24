"use client";

import { useState } from "react";
import useSWR from "swr";
import { productsApi, Product } from "@/lib/api";
import ProductCard from "@/components/products/ProductCard";
import Topbar from "@/components/layout/Topbar";
import { SlidersHorizontal, RefreshCw } from "lucide-react";

// The sources ingestion actually writes. "aliexpress" was listed here and has
// never produced a row; "1688" is the largest source and was missing, so
// filtering by it was impossible and picking aliexpress always returned none.
const SOURCES = ["all", "1688", "tiktok", "amazon"];

export default function TrendingPage() {
  const [source, setSource] = useState("all");
  const [minScore, setMinScore] = useState(50);

  const { data, isLoading, mutate } = useSWR(
    ["trending", source, minScore],
    () => productsApi.trending({
      source: source === "all" ? "" : source,
      min_score: minScore,
      limit: 40,
    }),
    { refreshInterval: 1_800_000 } // refresh every 30 min
  );

  const products: Product[] = data?.products ?? [];
  const isEmpty = !isLoading && products.length === 0;

  return (
    <div className="flex flex-col h-full">
      <Topbar title="Trending Products" />

      <div className="p-4 sm:p-6 space-y-6 flex-1">
        {/* Filters */}
        <div className="flex items-center gap-4 flex-wrap">
          <div className="flex items-center gap-2">
            <SlidersHorizontal size={14} className="text-zinc-500" />
            <span className="text-zinc-500 text-sm">Filters:</span>
          </div>

          {/* Source */}
          <div className="flex gap-1.5">
            {SOURCES.map((s) => (
              <button
                key={s}
                onClick={() => setSource(s)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium capitalize transition-colors
                  ${source === s
                    ? "bg-violet-600 text-white"
                    : "bg-zinc-800 text-zinc-400 hover:text-white"
                  }`}
              >
                {s}
              </button>
            ))}
          </div>

          <div className="w-px h-5 bg-zinc-700" />

          {/* Min score */}
          <div className="flex items-center gap-2">
            <span className="text-zinc-500 text-xs">Min score:</span>
            <input
              type="range"
              min={0}
              max={90}
              step={5}
              value={minScore}
              onChange={(e) => setMinScore(Number(e.target.value))}
              className="w-24 accent-violet-500"
            />
            <span className="text-violet-400 text-xs font-bold w-6">{minScore}</span>
          </div>

          <button
            onClick={() => mutate()}
            className="ml-auto flex items-center gap-1.5 text-xs text-zinc-500 hover:text-white transition-colors"
          >
            <RefreshCw size={12} />
            Refresh
          </button>
        </div>

        {/* Nothing matched. Say so — never substitute invented products. */}
        {isEmpty && (
          <div className="bg-zinc-900 border border-zinc-800 rounded-lg px-4 py-3 text-sm text-zinc-400">
            No products match these filters.{" "}
            <button
              onClick={() => {
                setSource("all");
                setMinScore(0);
              }}
              className="text-violet-400 hover:text-violet-300 underline"
            >
              Reset filters
            </button>
          </div>
        )}

        {/* Stats bar */}
        <div className="flex items-center gap-6 text-sm">
          <span className="text-zinc-500">
            <span className="text-white font-bold">{products.length}</span> products found
          </span>
          {products.length > 0 && (
            <span className="text-zinc-500">
              Avg score:{" "}
              <span className="text-violet-400 font-bold">
                {Math.round(products.reduce((a, p) => a + (p.score?.overall_score ?? 0), 0) / products.length)}
              </span>
            </span>
          )}
        </div>

        {/* Grid */}
        {isLoading ? (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
            {Array.from({ length: 20 }).map((_, i) => (
              <div key={i} className="bg-zinc-900 border border-zinc-800 rounded-xl aspect-[3/4] animate-pulse" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
            {products.map((product) => (
              <ProductCard key={product.id} product={product} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
