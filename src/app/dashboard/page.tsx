"use client";

import useSWR from "swr";
import { TrendingUp, Package, Bookmark, Zap } from "lucide-react";
import Topbar from "@/components/layout/Topbar";
import StatCard from "@/components/dashboard/StatCard";
import QuotaWidget from "@/components/dashboard/QuotaWidget";
import ScoreDistributionChart from "@/components/dashboard/ScoreDistributionChart";
import TopProductsMini from "@/components/dashboard/TopProductsMini";
import WatchlistMini from "@/components/dashboard/WatchlistMini";
import { usersApi, productsApi, watchlistApi, Me, Product, WatchlistItem } from "@/lib/api";

// Placeholder score distribution until we have a real /stats endpoint
const MOCK_DISTRIBUTION = [
  { range: "0–20",  count: 12 },
  { range: "21–40", count: 28 },
  { range: "41–60", count: 54 },
  { range: "61–80", count: 38 },
  { range: "81–100",count: 16 },
];

export default function DashboardPage() {
  const { data: me, isLoading: meLoading } = useSWR<Me>("me", usersApi.me);

  const { data: trendingData, isLoading: productsLoading } = useSWR(
    "dashboard-trending",
    () => productsApi.trending({ min_score: 60, limit: 10 }),
    { refreshInterval: 1_800_000 } // refresh every 30 min
  );

  const { data: watchlistData, isLoading: watchlistLoading } = useSWR(
    "dashboard-watchlist",
    watchlistApi.list
  );

  const products: Product[] = trendingData?.products ?? [];
  const watchlistItems: WatchlistItem[] = watchlistData?.items ?? [];
  const topScore = products.reduce((max, p) => Math.max(max, p.score?.overall_score ?? 0), 0);
  const plan = me?.subscription.plan ?? "free";

  return (
    <div className="flex flex-col min-h-full">
      <Topbar title="Overview" />

      <div className="p-6 space-y-6 flex-1">

        {/* Welcome banner */}
        <div className="bg-gradient-to-r from-violet-900/30 to-indigo-900/20 border border-violet-800/30 rounded-xl px-5 py-4 flex items-center justify-between">
          <div>
            <p className="text-white font-semibold text-sm">
              Good {getTimeOfDay()},{" "}
              <span className="text-violet-300">{me?.name ?? "..."}</span> 👋
            </p>
            <p className="text-zinc-500 text-xs mt-0.5">
              {products.length > 0
                ? `${products.length} products trending today. Top score: ${topScore}.`
                : "Scraper runs every 6 hours — check back soon for fresh products."}
            </p>
          </div>
          <div className={`text-xs font-bold px-3 py-1.5 rounded-full capitalize border
            ${plan === "pro" || plan === "agency"
              ? "bg-violet-600/20 text-violet-300 border-violet-600/30"
              : "bg-zinc-800 text-zinc-400 border-zinc-700"
            }`}
          >
            {plan} plan
          </div>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard
            label="Top Score Today"
            value={topScore || "—"}
            sub={topScore ? "AI-scored product" : "No data yet"}
            icon={TrendingUp}
            accent="violet"
            trend={topScore >= 75 ? "up" : "neutral"}
            trendValue={topScore >= 75 ? "Hot product detected" : ""}
          />
          <StatCard
            label="Products Tracked"
            value={trendingData?.total ?? "—"}
            sub="In today's feed"
            icon={Package}
            accent="blue"
          />
          <StatCard
            label="Watchlist"
            value={watchlistItems.length}
            sub={watchlistItems.length === 1 ? "product saved" : "products saved"}
            icon={Bookmark}
            accent="emerald"
          />
          <StatCard
            label="Searches Today"
            value={me?.quota.used ?? 0}
            sub={`of ${me?.quota.limit ?? 5} limit`}
            icon={Zap}
            accent="yellow"
            trend={
              !me ? "neutral"
              : me.quota.limit === "unlimited" ? "neutral"
              : Number(me.quota.used) / Number(me.quota.limit) >= 0.8 ? "down"
              : "up"
            }
            trendValue={
              me?.quota.limit === "unlimited"
                ? "Unlimited"
                : `${me?.quota.remaining ?? 0} remaining`
            }
          />
        </div>

        {/* Main content grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left col: top products */}
          <div className="lg:col-span-2 space-y-6">
            <TopProductsMini products={products} loading={productsLoading} />
            <ScoreDistributionChart data={MOCK_DISTRIBUTION} />
          </div>

          {/* Right col: quota + watchlist */}
          <div className="space-y-4">
            <QuotaWidget me={me} />
            <WatchlistMini items={watchlistItems} loading={watchlistLoading} />

            {/* Quick actions */}
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
              <h3 className="text-white font-semibold text-sm mb-3">Quick actions</h3>
              <div className="space-y-2">
                {[
                  { href: "/dashboard/trending", label: "Browse trending products", icon: "🔥" },
                  { href: "/dashboard/search",   label: "Search a keyword",         icon: "🔍" },
                  { href: "/dashboard/watchlist",label: "View my watchlist",        icon: "📌" },
                  { href: "/dashboard/billing",  label: "Manage subscription",      icon: "💳" },
                ].map(({ href, label, icon }) => (
                  <a
                    key={href}
                    href={href}
                    className="flex items-center gap-3 px-3 py-2.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 hover:text-white text-xs font-medium transition-colors"
                  >
                    <span>{icon}</span>
                    {label}
                  </a>
                ))}
              </div>
            </div>

            {/* Scraper status */}
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
              <h3 className="text-white font-semibold text-sm mb-3">Scraper status</h3>
              <div className="space-y-2.5">
                {[
                  { source: "AliExpress", status: "active", next: "in ~2h" },
                  { source: "TikTok Shop", status: "active", next: "in ~3h" },
                  { source: "AI Scoring",  status: "active", next: "at :30" },
                ].map(({ source, status, next }) => (
                  <div key={source} className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                      <span className="text-zinc-400">{source}</span>
                    </div>
                    <span className="text-zinc-600">Next run {next}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function getTimeOfDay(): string {
  const h = new Date().getHours();
  if (h < 12) return "morning";
  if (h < 17) return "afternoon";
  return "evening";
}
