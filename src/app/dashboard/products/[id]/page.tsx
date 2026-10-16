"use client";

import { useState } from "react";
import useSWR from "swr";
import { useParams } from "next/navigation";
import { productsApi, watchlistApi } from "@/lib/api";
import { formatPrice, sourceIcon, displayTitle, originalTitle, timeAgo } from "@/lib/utils";
import ScoreBadge from "@/components/products/ScoreBadge";
import ScoreBar from "@/components/products/ScoreBar";
import Topbar from "@/components/layout/Topbar";
import {
  ExternalLink, Bookmark, RefreshCw, Package,
  TrendingUp, ShoppingBag, Gauge, Truck, Store,
} from "lucide-react";
import { RadarChart, Radar, PolarGrid, PolarAngleAxis, ResponsiveContainer } from "recharts";
import ProductImage from "@/components/products/ProductImage";
import ProfitCalculator from "@/components/products/ProfitCalculator";
import QuoteForm from "@/components/products/QuoteForm";

export default function ProductDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [saved, setSaved] = useState(false);
  const [rescoring, setRescoring] = useState(false);
  const [activeImage, setActiveImage] = useState(0);
  const [quoteQty, setQuoteQty] = useState<number | null>(null);

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
        <div className="p-4 sm:p-6 animate-pulse space-y-4">
          <div className="h-8 w-64 bg-zinc-800 rounded" />
          <div className="h-96 bg-zinc-800 rounded-xl" />
        </div>
      </div>
    );
  }

  const details = product.details;
  const is1688 = product.source === "1688";
  const images = details?.images?.length ? details.images : product.image_url ? [product.image_url] : [];
  const mainImage = images[Math.min(activeImage, images.length - 1)] ?? null;

  const score = product.score;
  const radarData = score ? [
    { axis: "Demand", value: score.demand_score },
    { axis: "Margin", value: score.margin_score },
    { axis: "Low Competition", value: score.competition_score },
    { axis: "Trend", value: score.trend_score },
  ] : [];

  const facts = details ? [
    details.moq != null && { label: "Minimum order", value: `${details.moq.toLocaleString()}${details.unit ? ` ${details.unit}` : ""}` },
    details.units_sold != null && { label: "Sold on 1688", value: details.units_sold.toLocaleString() },
    details.ships_from && { label: "Ships from", value: details.ships_from },
    details.ships_within_days != null && { label: "Supplier dispatches within", value: `${details.ships_within_days} day${details.ships_within_days === 1 ? "" : "s"}` },
    details.weight_kg != null && { label: "Weight", value: `${details.weight_kg} kg` },
    { label: "Free delivery within China", value: details.free_shipping_in_china ? "Yes" : "No" },
    details.variants.length > 0 && { label: "Variants", value: String(details.variants.length) },
  ].filter(Boolean) as { label: string; value: string }[] : [];

  return (
    <div className="flex flex-col h-full">
      <Topbar title="Product Detail" />

      <div className="p-4 sm:p-6 max-w-6xl mx-auto w-full space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
          <div className="space-y-1 min-w-0">
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
            <h1 className="text-white text-xl font-bold leading-snug max-w-2xl">{displayTitle(product)}</h1>
            {originalTitle(product) && (
              <p lang="zh" className="text-zinc-500 text-sm mt-1 max-w-2xl">{originalTitle(product)}</p>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2 shrink-0">
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
              {is1688 ? "View on 1688" : "View product"}
            </a>
          </div>
        </div>

        {/* Main grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left: gallery + quick stats */}
          <div className="space-y-4">
            <div className="aspect-square bg-zinc-800 rounded-xl overflow-hidden">
              <ProductImage
                src={mainImage}
                alt={displayTitle(product)}
                className="w-full h-full object-cover"
                fallback={
                  <div className="w-full h-full flex items-center justify-center text-6xl">
                    {sourceIcon(product.source)}
                  </div>
                }
              />
            </div>
            {images.length > 1 && (
              <div className="flex gap-2 overflow-x-auto pb-1">
                {images.map((src, i) => (
                  <button
                    key={src}
                    onClick={() => setActiveImage(i)}
                    aria-label={`Photo ${i + 1}`}
                    className={`w-14 h-14 shrink-0 rounded-lg overflow-hidden border-2 ${i === activeImage ? "border-violet-500" : "border-transparent"}`}
                  >
                    <ProductImage src={src} alt="" className="w-full h-full object-cover" fallback={<div className="w-full h-full bg-zinc-800" />} />
                  </button>
                ))}
              </div>
            )}

            <div className="grid grid-cols-2 gap-3">
              {[
                { label: "Supplier cost", value: formatPrice(product.cost_usd), icon: Package },
                { label: product.price_is_derived ? "Suggested price" : "Sell price", value: formatPrice(product.price_usd), icon: ShoppingBag },
                { label: "Units sold", value: (details?.units_sold ?? product.orders_count)?.toLocaleString() ?? "N/A", icon: TrendingUp },
                { label: "Score", value: score ? `${score.overall_score}/100` : "N/A", icon: Gauge },
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
            {product.price_is_derived && (
              <p className="text-zinc-600 text-[11px] leading-relaxed">
                1688 lists wholesale cost only. The suggested price is a starting point — set your own in the profit calculator.
              </p>
            )}
          </div>

          {/* Center: score breakdown */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-5">
            <div className="flex items-center justify-between">
              <h2 className="text-white font-semibold">AI Score</h2>
              {score && <ScoreBadge score={score.overall_score} size="lg" />}
            </div>

            {score ? (
              <>
                <ResponsiveContainer width="100%" height={180}>
                  <RadarChart data={radarData}>
                    <PolarGrid stroke="#3f3f46" />
                    <PolarAngleAxis dataKey="axis" tick={{ fill: "#71717a", fontSize: 11 }} />
                    <Radar dataKey="value" stroke="#7c3aed" fill="#7c3aed" fillOpacity={0.3} />
                  </RadarChart>
                </ResponsiveContainer>

                <div className="space-y-3">
                  <ScoreBar label="Demand" score={score.demand_score} />
                  <ScoreBar label="Margin Potential" score={score.margin_score} />
                  <ScoreBar label="Low Competition" score={score.competition_score} />
                  <ScoreBar label="Trend Momentum" score={score.trend_score} />
                </div>

                {score.ai_summary && (
                  <div className="bg-violet-600/10 border border-violet-600/20 rounded-lg p-3">
                    <p className="text-violet-300 text-xs leading-relaxed">💡 {score.ai_summary}</p>
                  </div>
                )}
              </>
            ) : (
              <div className="flex items-center justify-center py-12 text-zinc-600 text-sm">
                No score yet — click Rescore
              </div>
            )}
          </div>

          {/* Right: sourcing */}
          <div className="space-y-4">
            {is1688 && (
              <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-4">
                <div className="flex items-center gap-2">
                  <Truck size={15} className="text-violet-400" />
                  <h2 className="text-white font-semibold">Sourcing</h2>
                </div>

                {details ? (
                  <>
                    {details.price_tiers.length > 0 && (
                      <div>
                        <div className="text-zinc-500 text-xs mb-2">Wholesale price by quantity</div>
                        <div className="divide-y divide-zinc-800 border border-zinc-800 rounded-lg overflow-hidden">
                          {details.price_tiers.map((t) => (
                            <div key={t.min_qty} className="flex items-center justify-between px-3 py-2 text-sm">
                              <span className="text-zinc-400">{t.min_qty.toLocaleString()}+ {details.unit ?? "units"}</span>
                              <span className="text-white font-medium">
                                {formatPrice(t.price_usd)} <span className="text-zinc-500 text-xs">¥{t.price_cny}</span>
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    <dl className="space-y-2 text-sm">
                      {facts.map(({ label, value }) => (
                        <div key={label} className="flex justify-between gap-3">
                          <dt className="text-zinc-500">{label}</dt>
                          <dd className="text-zinc-200 text-right">{value}</dd>
                        </div>
                      ))}
                    </dl>

                    {details.seller_name && (
                      <a
                        href={details.seller_url ?? product.product_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-2 p-3 bg-zinc-800 hover:bg-zinc-700 rounded-lg text-sm transition-colors"
                      >
                        <Store size={14} className="text-zinc-400 shrink-0" />
                        <span lang="zh" className="text-zinc-200 truncate">{details.seller_name}</span>
                        <ExternalLink size={12} className="text-zinc-500 shrink-0 ml-auto" />
                      </a>
                    )}

                    {details.fetched_at && (
                      <p className="text-zinc-600 text-[11px]">Supplier data from 1688, updated {timeAgo(details.fetched_at)}</p>
                    )}
                  </>
                ) : (
                  <p className="text-zinc-500 text-sm">
                    Price tiers and minimum order aren&apos;t loaded for this product yet. The cost shown is the
                    1688 search price. Request a quote for an exact number.
                  </p>
                )}
              </div>
            )}

            {/* Suppliers (retail sources, where a supplier was matched) */}
            {!is1688 && product.suppliers?.length > 0 && (
              <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
                <h2 className="text-white font-semibold mb-4">Suppliers</h2>
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
                        {(s.shipping_days > 0 || s.rating > 0) && (
                          <p className="text-zinc-500 text-xs">
                            {[s.shipping_days > 0 && `${s.shipping_days}d shipping`, s.rating > 0 && `⭐ ${s.rating}`].filter(Boolean).join(" · ")}
                          </p>
                        )}
                      </div>
                      <div className="text-right">
                        <p className="text-emerald-400 font-bold text-sm">{formatPrice(s.unit_cost_usd)}</p>
                        <p className="text-zinc-500 text-xs capitalize">{s.platform}</p>
                      </div>
                    </a>
                  ))}
                </div>
              </div>
            )}

            {/* Ad signals — only shown when we actually have some */}
            {product.ad_signals?.length > 0 && (
              <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
                <h2 className="text-white font-semibold mb-4">Ad Signals</h2>
                <div className="space-y-2">
                  {product.ad_signals.map((ad, i) => (
                    <div key={i} className="flex items-center justify-between p-3 bg-zinc-800 rounded-lg">
                      <span className="text-zinc-300 text-sm capitalize">{ad.platform}</span>
                      <div className="text-right">
                        <span className="text-white font-bold text-sm">{ad.ad_count} ads</span>
                        <p className="text-zinc-500 text-xs">Last seen: {new Date(ad.last_seen_at).toLocaleDateString()}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Profit calculator + product attributes */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            <ProfitCalculator product={product} onRequestQuote={(q) => setQuoteQty(q)} />
          </div>
          {details && Object.keys(details.attributes).length > 0 && (
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
              <h2 className="text-white font-semibold mb-3">Specifications</h2>
              <dl lang="zh" className="space-y-1.5 text-xs">
                {Object.entries(details.attributes).slice(0, 20).map(([k, v]) => (
                  <div key={k} className="flex justify-between gap-3">
                    <dt className="text-zinc-500 shrink-0">{k}</dt>
                    <dd className="text-zinc-300 text-right break-words">{v}</dd>
                  </div>
                ))}
              </dl>
            </div>
          )}
        </div>
      </div>

      <QuoteForm
        productId={product.id}
        productTitle={displayTitle(product)}
        initialQuantity={quoteQty ?? details?.moq ?? 1}
        open={quoteQty != null}
        onClose={() => setQuoteQty(null)}
      />
    </div>
  );
}
