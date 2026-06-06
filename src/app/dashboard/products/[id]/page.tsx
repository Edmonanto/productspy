"use client";

import { useState } from "react";
import useSWR from "swr";
import { useParams } from "next/navigation";
import { productsApi, watchlistApi } from "@/lib/api";
import { formatPrice, estimatedMargin, scoreColor, scoreLabel, sourceIcon } from "@/lib/utils";
import ScoreBadge from "@/components/products/ScoreBadge";
import ScoreBar from "@/components/products/ScoreBar";
import Topbar from "@/components/layout/Topbar";
import {
  ExternalLink, Bookmark, RefreshCw, Package,
  TrendingUp, ShoppingBag, Star
} from "lucide-react";
import { RadarChart, Radar, PolarGrid, PolarAngleAxis, ResponsiveContainer } from "recharts";

export default function ProductDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [saved, setSaved] = useState(false);
  const [rescoring, setRescoring] = useState(false);

  const { data: product, mutate, isLoading } = useSWR(
    id ? `product-${id}` : null,
    () => productsApi.detail(id)
  );

  const toggleWatchlist = async () => {
    if (!product) return;
    if (saved) {
      await watchlistApi.remove(product.id);
    } else {
      await watchlistApi.add(product.id);
    }
    setSaved(!saved);
  };

  const rescore = async () => {
    if (!product) return;
    setRescoring(true);
    try {
      await productsApi.rescore(product.id);
      await mutate();
    } finally {
      setRescoring(false);
    }
  };

  if (isLoading || !product) {
    return (
      <div className="flex flex-col h-full">
        <Topbar title="Product Detail" />
        <div className="p-6 animate-pulse space-y-4">
          <div className="h-8 w-64 bg-zinc-800 rounded" />
          <div className="h-96 bg-zinc-800 rounded-xl" />
        </div>
      </div>
    );
  }

  const score = product.score;
  const radarData = score ? [
    { axis: "Demand", value: score.demand_score },
    { axis: "Margin", value: score.margin_score },
    { axis: "Low Competition", value: score.competition_score },
    { axis: "Trend", value: score.trend_score },
  ] : [];

  return (
    <div className="flex flex-col h-full">
      <Topbar title="Product Detail" />

      <div className="p-6 max-w-6xl mx-auto w-full space-y-6">
        {/* Header */}
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2 text-zinc-500 text-sm">
              <span>{sourceIcon(product.source)}</span>
              <span className="capitalize">{product.source}</span>
              {product.category && (
                <>
                  <span>·</span>
                  <span>{product.category}</span>
                </>
              )}
            </div>
            <h1 className="text-white text-xl font-bold leading-snug max-w-2xl">{product.title}</h1>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={rescore}
              disabled={rescoring}
              className="flex items-center gap-1.5 px-3 py-2 bg-zinc-800 text-zinc-400 hover:text-white rounded-lg text-sm transition-colors"
            >
              <RefreshCw size={13} className={rescoring ? "animate-spin" : ""} />
              Rescore
            </button>
            <button
              onClick={toggleWatchlist}
              className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm transition-colors
                ${saved ? "bg-violet-600 text-white" : "bg-zinc-800 text-zinc-400 hover:text-white"}`}
            >
              <Bookmark size={13} fill={saved ? "currentColor" : "none"} />
              {saved ? "Saved" : "Save"}
            </button>
            <a
              href={product.product_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-3 py-2 bg-violet-600 hover:bg-violet-500 text-white rounded-lg text-sm transition-colors"
            >
              <ExternalLink size={13} />
              View Product
            </a>
          </div>
        </div>

        {/* Main grid */}
        <div className="grid grid-cols-3 gap-6">
          {/* Left: image + stats */}
          <div className="space-y-4">
            <div className="aspect-square bg-zinc-800 rounded-xl overflow-hidden">
              {product.image_url ? (
                <img src={product.image_url} alt={product.title} className="w-full h-full object-cover" />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-6xl">
                  {sourceIcon(product.source)}
                </div>
              )}
            </div>

            {/* Quick stats */}
            <div className="grid grid-cols-2 gap-3">
              {[
                { label: "Sell Price", value: formatPrice(product.price_usd), icon: ShoppingBag },
                { label: "COGS", value: formatPrice(product.cost_usd), icon: Package },
                { label: "Est. Margin", value: estimatedMargin(product.price_usd, product.cost_usd), icon: TrendingUp },
                { label: "Rating", value: product.score ? `${product.score.overall_score}/100` : "N/A", icon: Star },
              ].map(({ label, value, icon: Icon }) => (
                <div key={label} className="bg-zinc-900 border border-zinc-800 rounded-lg p-3">
                  <div className="flex items-center gap-1.5 text-zinc-500 text-xs mb-1">
                    <Icon size={11} />
                    {label}
                  </div>
                  <div className="text-white font-bold text-sm">{value}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Center: AI score breakdown */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-5">
            <div className="flex items-center justify-between">
              <h2 className="text-white font-semibold">AI Score</h2>
              {score && <ScoreBadge score={score.overall_score} size="lg" />}
            </div>

            {score ? (
              <>
                {/* Radar chart */}
                <ResponsiveContainer width="100%" height={180}>
                  <RadarChart data={radarData}>
                    <PolarGrid stroke="#3f3f46" />
                    <PolarAngleAxis dataKey="axis" tick={{ fill: "#71717a", fontSize: 11 }} />
                    <Radar
                      dataKey="value"
                      stroke="#7c3aed"
                      fill="#7c3aed"
                      fillOpacity={0.3}
                    />
                  </RadarChart>
                </ResponsiveContainer>

                {/* Score bars */}
                <div className="space-y-3">
                  <ScoreBar label="Demand" score={score.demand_score} />
                  <ScoreBar label="Margin Potential" score={score.margin_score} />
                  <ScoreBar label="Low Competition" score={score.competition_score} />
                  <ScoreBar label="Trend Momentum" score={score.trend_score} />
                </div>

                {/* AI summary */}
                {score.ai_summary && (
                  <div className="bg-violet-600/10 border border-violet-600/20 rounded-lg p-3">
                    <p className="text-violet-300 text-xs leading-relaxed">
                      💡 {score.ai_summary}
                    </p>
                  </div>
                )}
              </>
            ) : (
              <div className="flex items-center justify-center py-12 text-zinc-600 text-sm">
                No score yet — click Rescore
              </div>
            )}
          </div>

          {/* Right: suppliers + ad signals */}
          <div className="space-y-4">
            {/* Suppliers */}
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
              <h2 className="text-white font-semibold mb-4">Suppliers</h2>
              {product.suppliers?.length ? (
                <div className="space-y-3">
                  {product.suppliers.map((s, i) => (
                    <a
                      key={i}
                      href={s.supplier_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center justify-between p-3 bg-zinc-800 hover:bg-zinc-700 rounded-lg transition-colors"
                    >
                      <div>
                        <p className="text-white text-sm font-medium">{s.supplier_name || s.platform}</p>
                        <p className="text-zinc-500 text-xs">{s.shipping_days}d shipping · ⭐ {s.rating}</p>
                      </div>
                      <div className="text-right">
                        <p className="text-emerald-400 font-bold text-sm">{formatPrice(s.unit_cost_usd)}</p>
                        <p className="text-zinc-500 text-xs capitalize">{s.platform}</p>
                      </div>
                    </a>
                  ))}
                </div>
              ) : (
                <p className="text-zinc-600 text-sm">No suppliers found yet</p>
              )}
            </div>

            {/* Ad Signals */}
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
              <h2 className="text-white font-semibold mb-4">Ad Signals</h2>
              {product.ad_signals?.length ? (
                <div className="space-y-2">
                  {product.ad_signals.map((ad, i) => (
                    <div key={i} className="flex items-center justify-between p-3 bg-zinc-800 rounded-lg">
                      <span className="text-zinc-300 text-sm capitalize">{ad.platform}</span>
                      <div className="text-right">
                        <span className="text-white font-bold text-sm">{ad.ad_count} ads</span>
                        <p className="text-zinc-500 text-xs">
                          Last seen: {new Date(ad.last_seen_at).toLocaleDateString()}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex flex-col items-center py-6 text-center">
                  <p className="text-zinc-600 text-sm">No active ads detected</p>
                  <p className="text-zinc-700 text-xs mt-1">Could be early stage 👀</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
