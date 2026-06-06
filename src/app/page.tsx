import Link from "next/link";
import { Zap, TrendingUp, Shield, Search, ArrowRight, Check } from "lucide-react";

const FEATURES = [
  {
    icon: TrendingUp,
    title: "Real-time trend detection",
    desc: "Scrapes TikTok Shop, AliExpress, and Amazon daily. Know what's trending before it peaks.",
  },
  {
    icon: Zap,
    title: "AI product scoring",
    desc: "Every product gets a 0–100 score across demand, margin, competition, and trend momentum.",
  },
  {
    icon: Search,
    title: "Supplier matching",
    desc: "Auto-links each product to the best AliExpress and CJ suppliers with cost + shipping data.",
  },
  {
    icon: Shield,
    title: "Ad signal tracking",
    desc: "See if a product already has active TikTok or Meta ads — proof of market demand.",
  },
];

const PLANS = [
  {
    name: "Free",
    price: "$0",
    desc: "Try it out",
    features: ["5 searches/day", "Basic score", "No alerts"],
    cta: "Get started",
    highlight: false,
  },
  {
    name: "Pro",
    price: "$79",
    desc: "For serious dropshippers",
    features: [
      "Unlimited searches",
      "Full AI scoring",
      "Ad signal detection",
      "Supplier matching",
      "Email alerts",
      "Watchlist",
    ],
    cta: "Start free trial",
    highlight: true,
  },
  {
    name: "Agency",
    price: "$199",
    desc: "For teams & agencies",
    features: ["Everything in Pro", "5 seats", "White-label reports", "API access", "Priority support"],
    cta: "Contact us",
    highlight: false,
  },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-zinc-950 text-white">
      {/* Navbar */}
      <nav className="flex items-center justify-between px-8 py-5 border-b border-zinc-800 max-w-7xl mx-auto">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-violet-600 flex items-center justify-center">
            <Zap size={16} className="text-white" />
          </div>
          <span className="font-bold text-lg tracking-tight">ProductSpy AI</span>
        </div>
        <div className="flex items-center gap-6">
          <a href="#features" className="text-zinc-400 hover:text-white text-sm transition-colors">Features</a>
          <a href="#pricing" className="text-zinc-400 hover:text-white text-sm transition-colors">Pricing</a>
          <Link href="/login" className="text-zinc-400 hover:text-white text-sm transition-colors">Sign in</Link>
          <Link
            href="/signup"
            className="bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
          >
            Get started free
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="max-w-5xl mx-auto px-8 pt-24 pb-20 text-center space-y-8">
        <div className="inline-flex items-center gap-2 bg-violet-600/10 border border-violet-600/20 text-violet-400 text-xs font-medium px-3 py-1.5 rounded-full">
          🔥 AI-powered dropshipping product research
        </div>

        <h1 className="text-5xl md:text-6xl font-extrabold tracking-tight leading-tight">
          Find winning products{" "}
          <span className="bg-gradient-to-r from-violet-400 to-indigo-400 bg-clip-text text-transparent">
            before your competitors
          </span>
        </h1>

        <p className="text-zinc-400 text-lg max-w-2xl mx-auto">
          ProductSpy scans TikTok, AliExpress, and Amazon daily — then scores every product with AI
          so you know exactly what to sell and when.
        </p>

        <div className="flex items-center justify-center gap-4">
          <Link
            href="/signup"
            className="flex items-center gap-2 bg-violet-600 hover:bg-violet-500 text-white font-semibold px-6 py-3 rounded-xl transition-colors text-sm"
          >
            Start for free <ArrowRight size={16} />
          </Link>
          <Link
            href="/dashboard"
            className="flex items-center gap-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 font-semibold px-6 py-3 rounded-xl transition-colors text-sm"
          >
            View demo
          </Link>
        </div>

        <p className="text-zinc-600 text-xs">No credit card required · Free plan available</p>

        {/* Hero mockup */}
        <div className="mt-12 rounded-2xl border border-zinc-800 bg-zinc-900 p-4 shadow-2xl shadow-violet-900/20">
          <div className="flex items-center gap-2 mb-4 px-2">
            <div className="w-2.5 h-2.5 rounded-full bg-zinc-700" />
            <div className="w-2.5 h-2.5 rounded-full bg-zinc-700" />
            <div className="w-2.5 h-2.5 rounded-full bg-zinc-700" />
          </div>
          <div className="grid grid-cols-4 gap-3">
            {[
              { title: "LED Dog Collar", score: 87, price: "$24.99", margin: "72%" },
              { title: "Magnetic Phone Stand", score: 81, price: "$18.99", margin: "65%" },
              { title: "Portable Mini Projector", score: 76, price: "$49.99", margin: "58%" },
              { title: "Posture Corrector Belt", score: 73, price: "$22.99", margin: "61%" },
            ].map((p) => (
              <div key={p.title} className="bg-zinc-800 rounded-xl p-3 space-y-2">
                <div className="aspect-square bg-zinc-700 rounded-lg mb-2" />
                <p className="text-xs text-zinc-300 font-medium line-clamp-2">{p.title}</p>
                <div className="flex items-center justify-between">
                  <span className="text-emerald-400 font-bold text-xs">{p.score}</span>
                  <span className="text-zinc-500 text-xs">{p.margin} margin</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="max-w-5xl mx-auto px-8 py-20">
        <h2 className="text-3xl font-bold text-center mb-12">Everything you need to find winners</h2>
        <div className="grid grid-cols-2 gap-6">
          {FEATURES.map(({ icon: Icon, title, desc }) => (
            <div key={title} className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 space-y-3">
              <div className="w-10 h-10 rounded-lg bg-violet-600/20 flex items-center justify-center">
                <Icon size={18} className="text-violet-400" />
              </div>
              <h3 className="text-white font-semibold">{title}</h3>
              <p className="text-zinc-500 text-sm leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="max-w-5xl mx-auto px-8 py-20">
        <h2 className="text-3xl font-bold text-center mb-3">Simple, transparent pricing</h2>
        <p className="text-zinc-500 text-center text-sm mb-12">Cancel anytime. No lock-in.</p>

        <div className="grid grid-cols-3 gap-6">
          {PLANS.map((plan) => (
            <div
              key={plan.name}
              className={`rounded-2xl p-6 space-y-5 border ${
                plan.highlight
                  ? "bg-violet-600/10 border-violet-600/40 shadow-lg shadow-violet-900/20"
                  : "bg-zinc-900 border-zinc-800"
              }`}
            >
              {plan.highlight && (
                <div className="text-center">
                  <span className="bg-violet-600 text-white text-xs font-bold px-3 py-1 rounded-full">
                    MOST POPULAR
                  </span>
                </div>
              )}
              <div>
                <h3 className="text-white font-bold text-lg">{plan.name}</h3>
                <p className="text-zinc-500 text-sm">{plan.desc}</p>
              </div>
              <div>
                <span className="text-4xl font-extrabold text-white">{plan.price}</span>
                <span className="text-zinc-500 text-sm">/mo</span>
              </div>
              <ul className="space-y-2">
                {plan.features.map((f) => (
                  <li key={f} className="flex items-center gap-2 text-sm text-zinc-300">
                    <Check size={13} className="text-emerald-400 shrink-0" />
                    {f}
                  </li>
                ))}
              </ul>
              <Link
                href="/signup"
                className={`block text-center font-semibold py-2.5 rounded-xl text-sm transition-colors
                  ${plan.highlight
                    ? "bg-violet-600 hover:bg-violet-500 text-white"
                    : "bg-zinc-800 hover:bg-zinc-700 text-zinc-300"
                  }`}
              >
                {plan.cta}
              </Link>
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-zinc-800 px-8 py-8 max-w-7xl mx-auto flex items-center justify-between text-zinc-600 text-sm">
        <span>© 2026 ProductSpy AI</span>
        <div className="flex gap-6">
          <a href="#" className="hover:text-zinc-400 transition-colors">Privacy</a>
          <a href="#" className="hover:text-zinc-400 transition-colors">Terms</a>
          <a href="#" className="hover:text-zinc-400 transition-colors">Contact</a>
        </div>
      </footer>
    </div>
  );
}
