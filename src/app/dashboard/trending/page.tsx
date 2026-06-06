"use client";

import { useState } from "react";
import useSWR from "swr";
import { productsApi, Product } from "@/lib/api";
import { DEMO_PRODUCTS } from "@/lib/demo-products";
import ProductCard from "@/components/products/ProductCard";
import Topbar from "@/components/layout/Topbar";
import { SlidersHorizontal, RefreshCw } from "lucide-react";

const SOURCES = ["all", "aliexpress", "tiktok", "amazon"];
const CATEGORIES = ["all", "beauty", "electronics", "fashion", "home", "pets", "fitness"];

export default function TrendingPage() {
  const [source, setSource] = useState("all");
  const [category, setCategory] = useState("all");
  const [minScore, setMinScore] = useState(50);

  const { data, isLoading, mutate } = useSWR(
    ["trending", source, category, minScore],
    () => productsApi.trending({
      source,
      category: category === "all" ? "" : category,
      min_score: minScore,
      limit: 40,
    }),
    { refreshInterval: 1_800_000 } // refresh every 30 min
  );

  const apiProducts: Product[] = data?.products ?? [];
  const products: Product[] = apiProducts.length > 0 ? apiProducts : DEMO_PRODUCTS;

  return (
    <div className="flex flex-col h-full">
      <Topbar title="Trending Products" />

      <div className="p-6 space-y-6 flex-1">
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

          {/* Category */}
          <div className="flex gap-1.5 flex-wrap">
            {CATEGORIES.map((c) => (
              <button
                key={c}
                onClick={() => setCategory(c)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium capitalize transition-colors
                  ${category === c
                    ? "bg-zinc-600 text-white"
                    : "bg-zinc-800 text-zinc-400 hover:text-white"
                  }`}
              >
                {c}
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

        {/* Demo notice */}
        {apiProducts.length === 0 && !isLoading && (
          <div className="flex items-center gap-2 bg-violet-600/10 border border-violet-600/20 rounded-lg px-4 py-2.5 text-xs text-violet-300">
            <span>✨</span>
            <span>Showing sample products — your scraper will populate real data every 30 minutes once connected.</span>
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
