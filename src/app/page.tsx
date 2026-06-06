import Link from "next/link";
import { Zap, TrendingUp, Shield, Search, ArrowRight, Check, Star } from "lucide-react";

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
    features: ["Unlimited searches", "Full AI scoring", "Ad signal detection", "Supplier matching", "Email alerts", "Watchlist"],
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

const TESTIMONIALS = [
  { name: "Alex R.", role: "Dropshipper", text: "Found 3 winning products in my first week. ROI paid for itself day one.", stars: 5 },
  { name: "Maria T.", role: "Agency Owner", text: "We use it for all our clients. The AI scoring is scary accurate.", stars: 5 },
  { name: "Jason K.", role: "E-commerce founder", text: "Replaced 4 other tools. ProductSpy Pro does it all.", stars: 5 },
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
          ProductSpy Pro scans TikTok, AliExpress, and Amazon daily — then scores every product with AI so you know exactly what to sell and when.
        </p>
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
          <Link href="/signup" className="w-full sm:w-auto flex items-center justify-center gap-2 bg-violet-600 hover:bg-violet-500 text-white font-semibold px-6 py-3 rounded-xl transition-colors text-sm shadow-lg shadow-violet-900/30">
            Start for free <ArrowRight size={16} />
          </Link>
          <Link href="/dashboard" className="w-full sm:w-auto flex items-center justify-center gap-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 font-semibold px-6 py-3 rounded-xl transition-colors text-sm border border-zinc-700">
            View demo
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
            {[
              { title: "LED Dog Collar", score: 87, margin: "72%" },
              { title: "Magnetic Phone Stand", score: 81, margin: "65%" },
              { title: "Portable Mini Projector", score: 76, margin: "58%" },
              { title: "Posture Corrector Belt", score: 73, margin: "61%" },
            ].map((p) => (
              <div key={p.title} className="bg-zinc-800/80 rounded-xl p-3 space-y-2 border border-zinc-700/50">
                <div className="aspect-square bg-gradient-to-br from-zinc-700 to-zinc-800 rounded-lg mb-2" />
                <p className="text-xs text-zinc-300 font-medium line-clamp-2">{p.title}</p>
                <div className="flex items-center justify-between">
                  <span className="text-emerald-400 font-bold text-xs bg-emerald-500/10 px-1.5 py-0.5 rounded">{p.score}</span>
                  <span className="text-zinc-500 text-xs">{p.margin}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Social proof bar */}
      <section className="border-y border-zinc-800/60 py-6 bg-zinc-900/30">
        <div className="max-w-5xl mx-auto px-4 sm:px-8 flex flex-wrap items-center justify-center gap-4 sm:gap-12 text-zinc-500 text-xs sm:text-sm font-medium">
          {["10,000+ products tracked", "500+ active dropshippers", "3 marketplaces", "Updated every 30 min"].map((s) => (
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

      {/* Testimonials */}
      <section className="bg-zinc-900/40 border-y border-zinc-800/60 py-16 sm:py-20">
        <div className="max-w-5xl mx-auto px-4 sm:px-8">
          <h2 className="text-2xl sm:text-3xl font-bold text-center mb-10">Trusted by dropshippers worldwide</h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 sm:gap-6">
            {TESTIMONIALS.map((t) => (
              <div key={t.name} className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-4">
                <div className="flex gap-0.5">
                  {Array.from({ length: t.stars }).map((_, i) => (
                    <Star key={i} size={14} className="text-yellow-400 fill-yellow-400" />
                  ))}
                </div>
                <p className="text-zinc-300 text-sm leading-relaxed">"{t.text}"</p>
                <div>
                  <p className="text-white text-sm font-semibold">{t.name}</p>
                  <p className="text-zinc-500 text-xs">{t.role}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="max-w-5xl mx-auto px-4 sm:px-8 py-16 sm:py-20">
        <div className="text-center mb-10 sm:mb-12">
          <h2 className="text-2xl sm:text-3xl font-bold mb-3">Simple, transparent pricing</h2>
          <p className="text-zinc-500 text-sm">Cancel anytime. No lock-in.</p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 sm:gap-6">
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
                <span className="text-zinc-500 text-sm">/mo</span>
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
            Join 500+ dropshippers using ProductSpy Pro to source smarter and scale faster.
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
