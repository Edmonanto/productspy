import Link from "next/link";
import {
  Zap, ArrowRight, Check, Trophy, Radar, Brain, Gauge, CheckCircle2, AlertTriangle, Globe2,
} from "lucide-react";

// What the product does, in the order it does it. Each claim here maps to
// code: backend/app/winners/ (collectors, extract, scoring, worker).
const STEPS = [
  {
    icon: Radar,
    title: "We read the ads, every day",
    desc: "The Facebook Ad Library, TikTok's Top Ads and product videos on TikTok — per country, once a day. How long each ad has been running, how many versions, how many stores, how people react.",
  },
  {
    icon: Brain,
    title: "AI turns ads into products",
    desc: "Claude names the product behind every ad, merges duplicates across stores and platforms, and flags brand copies, restricted items and fragile goods before they reach you.",
  },
  {
    icon: Gauge,
    title: "Only the best make the list",
    desc: "Every product is scored 0–100 on five signals. 5–10 products scoring 70+ become that day's winners — each with its reasons, its weak points and the ads behind it. Like one? Work out your profit, then request an exact sourcing quote for your quantity and country.",
  },
];

// How the score is weighted — see backend/app/winners/scoring.py.
const SCORE_PARTS = [
  { label: "Scaling proof", pts: 30, desc: "Advertisers keep paying: ads running 14+ days, 5+ versions, new versions launched this week." },
  { label: "Engagement", pts: 25, desc: "TikTok engagement rate, shares, and the share of comments asking “where can I buy this?”." },
  { label: "Proven demand", pts: 20, desc: "3–15 different stores selling it — validated, not saturated — plus creators and views." },
  { label: "Margin", pts: 15, desc: "Sells for 3× the supplier cost or more, ideally in the $20–60 range." },
  { label: "Freshness", pts: 10, desc: "New, accelerating, and with a wow effect or a real problem solved." },
];

const MARKETS = [
  "🇺🇸 United States", "🇬🇧 United Kingdom", "🇪🇺 Europe", "🇫🇷 France", "🇩🇪 Germany",
  "🇨🇦 Canada", "🇦🇺 Australia", "🇦🇪 UAE / Dubai", "🇸🇦 Saudi Arabia",
];

const PLANS = [
  {
    name: "Free",
    price: "$0",
    desc: "After your trial",
    features: ["Top 3 Daily Winners a day", "1 market", "Score + reasons for each pick", "Watchlist (10 products)"],
    cta: "Start free",
    highlight: false,
  },
  {
    name: "Starter",
    price: "$29",
    desc: "For one store",
    features: ["All 5–10 Daily Winners", "1 market", "Ad & video evidence", "7-day archive"],
    cta: "Start with Starter",
    highlight: false,
  },
  {
    name: "Pro",
    price: "$79",
    desc: "For serious dropshippers",
    features: ["All 5–10 Daily Winners", "3 markets", "Ad & video evidence + suppliers", "30-day archive + CSV export", "Priority support"],
    cta: "Start 7-day free trial",
    highlight: true,
  },
  {
    name: "Agency",
    price: "$199",
    desc: "For teams & agencies",
    features: ["Everything in Pro", "Every market", "90-day archive", "Dedicated support"],
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
            <a href="#how" className="text-zinc-400 hover:text-white text-sm transition-colors">How it works</a>
            <a href="#pricing" className="text-zinc-400 hover:text-white text-sm transition-colors">Pricing</a>
            <Link href="/login" className="text-zinc-400 hover:text-white text-sm transition-colors">Sign in</Link>
            <Link href="/signup" className="bg-violet-600 hover:bg-violet-500 text-white text-sm font-semibold px-4 py-2 rounded-lg transition-colors shadow-lg shadow-violet-900/30">
              Start free trial
            </Link>
          </div>
          <Link href="/signup" className="sm:hidden bg-violet-600 hover:bg-violet-500 text-white text-xs font-semibold px-3 py-2 rounded-lg transition-colors">
            Free trial
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="max-w-5xl mx-auto px-4 sm:px-8 pt-16 sm:pt-24 pb-16 sm:pb-20 text-center space-y-6 sm:space-y-8">
        <div className="inline-flex items-center gap-2 bg-violet-600/10 border border-violet-600/20 text-violet-400 text-xs font-semibold px-3 py-1.5 rounded-full">
          <Trophy size={13} /> New winning products every morning
        </div>
        <h1 className="text-4xl sm:text-5xl md:text-6xl font-extrabold tracking-tight leading-tight">
          The products advertisers are{" "}
          <span className="bg-gradient-to-r from-violet-400 to-indigo-400 bg-clip-text text-transparent">
            scaling right now
          </span>
        </h1>
        <p className="text-zinc-400 text-base sm:text-lg max-w-2xl mx-auto leading-relaxed">
          ProductSpy Pro reads the Facebook Ad Library, TikTok&apos;s Top Ads and TikTok every day, in your market,
          and hands you the 5–10 strongest products — with the ads, stores and margins behind each one.
        </p>
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
          <Link href="/signup" className="w-full sm:w-auto flex items-center justify-center gap-2 bg-violet-600 hover:bg-violet-500 text-white font-semibold px-6 py-3 rounded-xl transition-colors text-sm shadow-lg shadow-violet-900/30">
            Start 7-day free trial <ArrowRight size={16} />
          </Link>
          <Link href="/login" className="w-full sm:w-auto flex items-center justify-center gap-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 font-semibold px-6 py-3 rounded-xl transition-colors text-sm border border-zinc-700">
            Sign in
          </Link>
        </div>
        <p className="text-zinc-600 text-xs">7 days of Pro free · No credit card required · Free plan after the trial</p>

        {/* Anatomy of a pick — a layout illustration, not a real product */}
        <div className="mt-8 sm:mt-12 rounded-2xl border border-zinc-800 bg-zinc-900/80 p-4 sm:p-6 shadow-2xl shadow-violet-900/20 ring-1 ring-white/5 text-left">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-2.5 h-2.5 rounded-full bg-red-500/70" />
            <div className="w-2.5 h-2.5 rounded-full bg-yellow-500/70" />
            <div className="w-2.5 h-2.5 rounded-full bg-green-500/70" />
            <span className="text-zinc-600 text-xs ml-2">productspy.pro/dashboard/winners</span>
          </div>
          <div className="flex flex-col md:flex-row gap-5">
            <div className="w-full md:w-32 aspect-square md:h-32 rounded-xl bg-gradient-to-br from-zinc-700 to-zinc-800 flex items-center justify-center text-zinc-500 text-xs shrink-0">
              product photo
            </div>
            <div className="flex-1 space-y-2.5">
              <div className="text-white font-semibold">#1 · the product name</div>
              <div className="flex flex-wrap gap-1.5 text-[11px]">
                {["Facebook Ads", "TikTok Ads", "TikTok", "high confidence"].map((t) => (
                  <span key={t} className="bg-zinc-800 text-zinc-300 rounded px-1.5 py-0.5">{t}</span>
                ))}
              </div>
              <ul className="space-y-1 text-sm">
                {["How long its ads have been running", "How many stores sell it — validated, not saturated", "How much of the audience asks where to buy it"].map((r) => (
                  <li key={r} className="flex gap-2 text-zinc-300"><CheckCircle2 size={14} className="text-emerald-400 mt-0.5 shrink-0" />{r}</li>
                ))}
                <li className="flex gap-2 text-zinc-400"><AlertTriangle size={14} className="text-amber-400 mt-0.5 shrink-0" />Its weak points, said plainly</li>
              </ul>
            </div>
            <div className="md:w-56 space-y-1.5 md:border-l md:border-zinc-800 md:pl-5">
              <div className="text-zinc-500 text-xs mb-2">Score out of 100</div>
              {SCORE_PARTS.map((p) => (
                <div key={p.label} className="flex items-center gap-2 text-[11px]">
                  <span className="w-24 text-zinc-400 shrink-0">{p.label}</span>
                  <div className="flex-1 h-1.5 bg-zinc-800 rounded-full"><div className="h-full bg-violet-500/60 rounded-full" style={{ width: "100%" }} /></div>
                  <span className="text-zinc-500 w-6 text-right">{p.pts}</span>
                </div>
              ))}
            </div>
          </div>
          <p className="text-zinc-600 text-[11px] mt-4">How every pick is laid out. Real picks show real products, prices and the ads behind them.</p>
        </div>
      </section>

      {/* Facts bar */}
      <section className="border-y border-zinc-800/60 py-6 bg-zinc-900/30">
        <div className="max-w-5xl mx-auto px-4 sm:px-8 flex flex-wrap items-center justify-center gap-x-10 gap-y-3 text-zinc-500 text-xs sm:text-sm font-medium">
          {["Facebook Ad Library · TikTok Top Ads · TikTok", "New picks every morning", "9 markets", "Exact sourcing quotes on request"].map((s) => (
            <span key={s} className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-violet-500 shrink-0" />
              {s}
            </span>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="max-w-5xl mx-auto px-4 sm:px-8 py-16 sm:py-20">
        <div className="text-center mb-10 sm:mb-12">
          <h2 className="text-2xl sm:text-3xl font-bold mb-3">From thousands of ads to a short list</h2>
          <p className="text-zinc-500 text-sm">So you spend your budget testing products that already have proof.</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 sm:gap-6">
          {STEPS.map(({ icon: Icon, title, desc }, i) => (
            <div key={title} className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 sm:p-6 space-y-3 hover:border-zinc-700 transition-colors">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-violet-600/20 border border-violet-600/20 flex items-center justify-center">
                  <Icon size={18} className="text-violet-400" />
                </div>
                <span className="text-zinc-600 text-sm font-semibold">Step {i + 1}</span>
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
              Five signals, shown separately on every pick. Missing data never counts as good news, and saturated
              products, brand copies and restricted items are removed before scoring.
            </p>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
            {SCORE_PARTS.map((p) => (
              <div key={p.label} className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-2">
                <div className="flex items-baseline justify-between">
                  <span className="text-white font-semibold text-sm">{p.label}</span>
                  <span className="text-violet-400 font-bold text-sm">{p.pts}</span>
                </div>
                <p className="text-zinc-500 text-xs leading-relaxed">{p.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Markets */}
      <section className="max-w-5xl mx-auto px-4 sm:px-8 py-16 sm:py-20 text-center">
        <h2 className="text-2xl sm:text-3xl font-bold mb-3 flex items-center justify-center gap-2"><Globe2 size={24} className="text-violet-400" /> Picked for your market</h2>
        <p className="text-zinc-500 text-sm mb-8">What wins in Dubai isn&apos;t what wins in Texas. Each market gets its own scan and its own list.</p>
        <div className="flex flex-wrap justify-center gap-2">
          {MARKETS.map((m) => (
            <span key={m} className="bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-300">{m}</span>
          ))}
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="max-w-5xl mx-auto px-4 sm:px-8 pb-16 sm:pb-20">
        <div className="text-center mb-10 sm:mb-12">
          <h2 className="text-2xl sm:text-3xl font-bold mb-3">Simple, transparent pricing</h2>
          <p className="text-zinc-500 text-sm">Every account starts with 7 days of Pro, free. Cancel anytime.</p>
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
          <h2 className="text-2xl sm:text-3xl font-bold">Tomorrow morning, your first list of winners</h2>
          <p className="text-zinc-400 text-sm sm:text-base max-w-xl mx-auto">
            7 days of Pro free, no card. See the products, the ads and the reasons behind them —
            and upgrade only if it earns it.
          </p>
          <Link href="/signup" className="inline-flex items-center gap-2 bg-violet-600 hover:bg-violet-500 text-white font-semibold px-8 py-3.5 rounded-xl transition-colors text-sm shadow-lg shadow-violet-900/40">
            Start your 7-day free trial <ArrowRight size={16} />
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
