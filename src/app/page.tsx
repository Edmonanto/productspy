import Link from "next/link";
import { Zap, TrendingUp, GitCompareArrows, LineChart, ArrowRight, Check } from "lucide-react";
import ProductImage from "@/components/products/ProductImage";

const FEATURES = [
  {
    icon: TrendingUp,
    title: "Three sources, every six hours",
    desc: "TikTok Shop for retail price and units sold, 1688 for real wholesale cost, Amazon as a retail price anchor. Ingested on a schedule, not on demand.",
  },
  {
    icon: Zap,
    title: "Scored 0-100, and told why",
    desc: "Demand, margin, trend and competition, weighted and shown separately. A signal we don't have scores neutral instead of being guessed at — so a high score means evidence, not optimism.",
  },
  {
    icon: GitCompareArrows,
    title: "Retail matched to supplier",
    desc: "Pairs a retail listing with the 1688 offer behind it, so margin comes from two observed numbers. Every match goes to a review queue — nothing is applied to your data automatically.",
  },
  {
    icon: LineChart,
    title: "Trend from our own history",
    desc: "Order velocity is measured across our own snapshots over time rather than bought from a provider, so it reflects what actually moved.",
  },
];

// A real slice of the catalogue, captured from the live database. Prices and
// scores are the stored values; 1688 has no retail price, so the figure shown
// for it is derived from cost and labelled as an estimate.
const SHOWCASE = [
  {
    source: "amazon",
    title: "Whiskers & Friends Cat Bed for Indoor Cats & Small Dogs, Fluffy",
    price: "$24.95",
    derived: false,
    score: 50,
    image: "https://m.media-amazon.com/images/I/71ea24NOlQL._AC_UL320_.jpg",
  },
  {
    source: "1688",
    title: "兰猫宠王剑麻黄麻猫抓板猫窝一体简约大型猫咪免安装宠物用品",
    price: "$6.66",
    derived: true,
    score: 64,
    image: "https://cbu01.alicdn.com/img/ibank/O1CN01h4ciFS1wVPW7ISNMN_!!2222710966313-0-cib.jpg",
  },
  {
    source: "amazon",
    title: "Love's cabin Round Donut Cat and Dog Cushion Bed, 20in",
    price: "$15.99",
    derived: false,
    score: 50,
    image: "https://m.media-amazon.com/images/I/91ohn1BKStL._AC_UL320_.jpg",
  },
  {
    source: "1688",
    title: "冬季保暖贝壳半封闭猫窝宠物猫床半包围狗窝狗床封闭式猫咪窝",
    price: "$16.77",
    derived: true,
    score: 64,
    image: "https://cbu01.alicdn.com/img/ibank/O1CN01Qo3Mme1wQp5HJhDjG_!!2206895696303-0-cib.jpg",
  },
];

const SOURCE_LABEL: Record<string, string> = {
  "1688": "🏭 1688",
  amazon: "📦 amazon",
  tiktok: "🎵 tiktok",
};

// How the composite is actually weighted — see backend/app/scoring.py.
const SCORE_PARTS = [
  { label: "Demand", weight: "30%", desc: "Units sold, ranked against the product's own marketplace rather than across them." },
  { label: "Margin", weight: "30%", desc: "Retail minus supplier cost, counted only when both numbers were observed." },
  { label: "Trend", weight: "25%", desc: "Change in order velocity across our own snapshot history." },
  { label: "Competition", weight: "15%", desc: "Advertiser volume. Not yet collected, so it currently scores neutral for everything." },
];

const PLANS = [
  {
    name: "Free",
    price: "$0",
    desc: "Try it out",
    features: ["5 searches/day", "Full product scores", "Watchlist (10 products)"],
    cta: "Get started",
    highlight: false,
  },
  {
    name: "Starter",
    price: "$29",
    desc: "For one store",
    features: ["50 searches/day", "Full product scores", "Unlimited watchlist", "Email alerts"],
    cta: "Start with Starter",
    highlight: false,
  },
  {
    name: "Pro",
    price: "$79",
    desc: "For serious dropshippers",
    features: ["Unlimited searches", "Full product scores", "Supplier matching", "Email alerts", "Priority support"],
    cta: "Start free trial",
    highlight: true,
  },
  {
    name: "Agency",
    price: "$199",
    desc: "For teams & agencies",
    features: ["Everything in Pro", "5 team seats", "White-label reports", "API access", "Dedicated support"],
    cta: "Contact us",
    highlight: false,
  },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-zinc-950 text-white">

      {/* Navbar */}
      <nav className="sticky top-0 z-50 bg-zinc-950/80 backdrop-blur-md border-b border-zinc-800/60">
        <div className="flex items-center justify-between px-4 sm:px-8 py-4 max-w-7xl mx-auto">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-600 to-indigo-600 flex items-center justify-center shadow-lg shadow-violet-900/40">
              <Zap size={16} className="text-white" />
            </div>
            <span className="font-bold text-white text-base sm:text-lg tracking-tight">ProductSpy</span>
            <span className="text-[10px] text-violet-400 font-bold bg-violet-500/10 border border-violet-500/20 px-1.5 py-0.5 rounded">PRO</span>
          </div>
          <div className="hidden sm:flex items-center gap-6">
            <a href="#features" className="text-zinc-400 hover:text-white text-sm transition-colors">Features</a>
            <a href="#pricing" className="text-zinc-400 hover:text-white text-sm transition-colors">Pricing</a>
            <Link href="/login" className="text-zinc-400 hover:text-white text-sm transition-colors">Sign in</Link>
            <Link href="/signup" className="bg-violet-600 hover:bg-violet-500 text-white text-sm font-semibold px-4 py-2 rounded-lg transition-colors shadow-lg shadow-violet-900/30">
              Get started free
            </Link>
          </div>
          <Link href="/signup" className="sm:hidden bg-violet-600 hover:bg-violet-500 text-white text-xs font-semibold px-3 py-2 rounded-lg transition-colors">
            Get started
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="max-w-5xl mx-auto px-4 sm:px-8 pt-16 sm:pt-24 pb-16 sm:pb-20 text-center space-y-6 sm:space-y-8">
        <div className="inline-flex items-center gap-2 bg-violet-600/10 border border-violet-600/20 text-violet-400 text-xs font-semibold px-3 py-1.5 rounded-full">
          🔥 AI-powered dropshipping product research
        </div>
        <h1 className="text-4xl sm:text-5xl md:text-6xl font-extrabold tracking-tight leading-tight">
          Find winning products{" "}
          <span className="bg-gradient-to-r from-violet-400 to-indigo-400 bg-clip-text text-transparent">
            before your competitors
          </span>
        </h1>
        <p className="text-zinc-400 text-base sm:text-lg max-w-2xl mx-auto leading-relaxed">
          ProductSpy Pro ingests TikTok Shop, 1688 and Amazon every six hours, scores every product on demand, margin and trend, and matches retail listings to the supplier behind them.
        </p>
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
          <Link href="/signup" className="w-full sm:w-auto flex items-center justify-center gap-2 bg-violet-600 hover:bg-violet-500 text-white font-semibold px-6 py-3 rounded-xl transition-colors text-sm shadow-lg shadow-violet-900/30">
            Start for free <ArrowRight size={16} />
          </Link>
          <Link href="/login" className="w-full sm:w-auto flex items-center justify-center gap-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 font-semibold px-6 py-3 rounded-xl transition-colors text-sm border border-zinc-700">
            Sign in
          </Link>
        </div>
        <p className="text-zinc-600 text-xs">No credit card required · Free plan available · Cancel anytime</p>

        {/* Hero mockup */}
        <div className="mt-8 sm:mt-12 rounded-2xl border border-zinc-800 bg-zinc-900/80 p-3 sm:p-4 shadow-2xl shadow-violet-900/20 ring-1 ring-white/5">
          <div className="flex items-center gap-2 mb-4 px-2">
            <div className="w-2.5 h-2.5 rounded-full bg-red-500/70" />
            <div className="w-2.5 h-2.5 rounded-full bg-yellow-500/70" />
            <div className="w-2.5 h-2.5 rounded-full bg-green-500/70" />
            <span className="text-zinc-600 text-xs ml-2">productspy.pro/dashboard</span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 sm:gap-3">
            {SHOWCASE.map((p) => (
              <div key={p.title} className="bg-zinc-800/80 rounded-xl p-3 space-y-2 border border-zinc-700/50 text-left">
                <div className="aspect-square rounded-lg overflow-hidden bg-zinc-700/60">
                  <ProductImage
                    src={p.image}
                    alt={p.title}
                    className="w-full h-full object-cover"
                    fallback={<div className="w-full h-full bg-gradient-to-br from-zinc-700 to-zinc-800" />}
                  />
                </div>
                <p className="text-[10px] text-zinc-500">{SOURCE_LABEL[p.source]}</p>
                <p className="text-xs text-zinc-300 font-medium line-clamp-2">{p.title}</p>
                <div className="flex items-center justify-between">
                  <span className="text-emerald-400 font-bold text-xs bg-emerald-500/10 px-1.5 py-0.5 rounded">{p.score}</span>
                  <span className="text-zinc-500 text-xs">
                    {p.derived && <span className="text-zinc-600">est. </span>}{p.price}
                  </span>
                </div>
              </div>
            ))}
          </div>
          <p className="text-zinc-600 text-[11px] mt-3 px-2">
            Real listings and stored scores from the catalogue. 1688 publishes no
            retail price, so its figure is derived from cost and marked as an estimate.
          </p>
        </div>
      </section>

      {/* Social proof bar */}
      <section className="border-y border-zinc-800/60 py-6 bg-zinc-900/30">
        <div className="max-w-5xl mx-auto px-4 sm:px-8 flex flex-wrap items-center justify-center gap-4 sm:gap-12 text-zinc-500 text-xs sm:text-sm font-medium">
          {["TikTok Shop · 1688 · Amazon", "Refreshed every 6 hours", "Four scoring signals", "Supplier matches reviewed, never auto-applied"].map((s) => (
            <span key={s} className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-violet-500 shrink-0" />
              {s}
            </span>
          ))}
        </div>
      </section>

      {/* Features */}
      <section id="features" className="max-w-5xl mx-auto px-4 sm:px-8 py-16 sm:py-20">
        <div className="text-center mb-10 sm:mb-12">
          <h2 className="text-2xl sm:text-3xl font-bold mb-3">Everything you need to find winners</h2>
          <p className="text-zinc-500 text-sm">Built for dropshippers who want an edge — not more guesswork.</p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-6">
          {FEATURES.map(({ icon: Icon, title, desc }) => (
            <div key={title} className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 sm:p-6 space-y-3 hover:border-zinc-700 transition-colors group">
              <div className="w-10 h-10 rounded-lg bg-violet-600/20 border border-violet-600/20 flex items-center justify-center group-hover:bg-violet-600/30 transition-colors">
                <Icon size={18} className="text-violet-400" />
              </div>
              <h3 className="text-white font-semibold">{title}</h3>
              <p className="text-zinc-500 text-sm leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How the score is built */}
      <section className="bg-zinc-900/40 border-y border-zinc-800/60 py-16 sm:py-20">
        <div className="max-w-5xl mx-auto px-4 sm:px-8">
          <div className="text-center mb-10">
            <h2 className="text-2xl sm:text-3xl font-bold mb-3">What the score is made of</h2>
            <p className="text-zinc-500 text-sm max-w-2xl mx-auto">
              One number is easy to distrust, so here is the whole of it. Each part
              is shown separately in the dashboard alongside the total.
            </p>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-6">
            {SCORE_PARTS.map((part) => (
              <div key={part.label} className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-2">
                <div className="flex items-baseline justify-between gap-3">
                  <h3 className="text-white font-semibold">{part.label}</h3>
                  <span className="text-violet-400 text-sm font-bold">{part.weight}</span>
                </div>
                <p className="text-zinc-500 text-sm leading-relaxed">{part.desc}</p>
              </div>
            ))}
          </div>
          <p className="text-zinc-600 text-xs text-center mt-6 max-w-2xl mx-auto">
            Where a signal is missing it scores the neutral midpoint rather than zero,
            so a product is never buried for a number its marketplace simply doesn&apos;t publish.
          </p>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="max-w-5xl mx-auto px-4 sm:px-8 py-16 sm:py-20">
        <div className="text-center mb-10 sm:mb-12">
          <h2 className="text-2xl sm:text-3xl font-bold mb-3">Simple, transparent pricing</h2>
          <p className="text-zinc-500 text-sm">Cancel anytime. No lock-in.</p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
          {PLANS.map((plan) => (
            <div key={plan.name} className={`rounded-2xl p-5 sm:p-6 space-y-5 border transition-all ${
              plan.highlight
                ? "bg-violet-600/10 border-violet-600/40 shadow-lg shadow-violet-900/20 ring-1 ring-violet-500/20"
                : "bg-zinc-900 border-zinc-800 hover:border-zinc-700"
            }`}>
              {plan.highlight && (
                <div className="text-center">
                  <span className="bg-violet-600 text-white text-xs font-bold px-3 py-1 rounded-full">MOST POPULAR</span>
                </div>
              )}
              <div>
                <h3 className="text-white font-bold text-lg">{plan.name}</h3>
                <p className="text-zinc-500 text-sm">{plan.desc}</p>
              </div>
              <div>
                <span className="text-4xl font-extrabold text-white">{plan.price}</span>
                {plan.price !== "$0" && <span className="text-zinc-500 text-sm">/mo</span>}
              </div>
              <ul className="space-y-2.5">
                {plan.features.map((f) => (
                  <li key={f} className="flex items-center gap-2 text-sm text-zinc-300">
                    <Check size={13} className="text-emerald-400 shrink-0" />
                    {f}
                  </li>
                ))}
              </ul>
              <Link href="/signup" className={`block text-center font-semibold py-2.5 rounded-xl text-sm transition-colors ${
                plan.highlight
                  ? "bg-violet-600 hover:bg-violet-500 text-white shadow-lg shadow-violet-900/30"
                  : "bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border border-zinc-700"
              }`}>
                {plan.cta}
              </Link>
            </div>
          ))}
        </div>
      </section>

      {/* CTA banner */}
      <section className="max-w-5xl mx-auto px-4 sm:px-8 pb-16 sm:pb-20">
        <div className="bg-gradient-to-r from-violet-900/40 to-indigo-900/30 border border-violet-800/40 rounded-2xl p-8 sm:p-12 text-center space-y-5">
          <h2 className="text-2xl sm:text-3xl font-bold">Ready to find your next winning product?</h2>
          <p className="text-zinc-400 text-sm sm:text-base max-w-xl mx-auto">
            Start on the free plan, see the scores and the evidence behind them,
            and upgrade only if it earns it.
          </p>
          <Link href="/signup" className="inline-flex items-center gap-2 bg-violet-600 hover:bg-violet-500 text-white font-semibold px-8 py-3.5 rounded-xl transition-colors text-sm shadow-lg shadow-violet-900/40">
            Start for free — no card required <ArrowRight size={16} />
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-zinc-800 px-4 sm:px-8 py-8">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4 text-zinc-600 text-sm">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded bg-gradient-to-br from-violet-600 to-indigo-600 flex items-center justify-center">
              <Zap size={12} className="text-white" />
            </div>
            <span className="text-zinc-500 font-medium">ProductSpy Pro</span>
            <span>© 2026</span>
          </div>
          <div className="flex gap-6">
            <a href="#" className="hover:text-zinc-400 transition-colors">Privacy</a>
            <a href="#" className="hover:text-zinc-400 transition-colors">Terms</a>
            <a href="#" className="hover:text-zinc-400 transition-colors">Contact</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
