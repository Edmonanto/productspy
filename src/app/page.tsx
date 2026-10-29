import Link from "next/link";
import {
  ArrowRight, BarChart3, Brain, Calculator, Check, Clock, FileSearch, GitCompare, Handshake, Lightbulb,
  Radar as RadarIcon, ShieldCheck, Sparkles, TrendingUp, X, Zap,
} from "lucide-react";
import { ReviewsSection, TrustedBySection } from "@/components/landing/SocialProof";
import { SiteFooter } from "@/components/legal/LegalPage";
import LivePicks, { type Preview } from "@/components/landing/LivePicks";
import MiniProfitCalc from "@/components/landing/MiniProfitCalc";
import { CriteriaRadar } from "@/components/visual/Visuals";
import { SITE } from "@/lib/site";

export const revalidate = 600;

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

async function getPreview(): Promise<Preview | null> {
  try {
    const r = await fetch(`${API}/winners/preview`, { next: { revalidate: 600 }, signal: AbortSignal.timeout(5000) });
    return r.ok ? ((await r.json()) as Preview) : null;
  } catch {
    return null;
  }
}

// Same 8 criteria and weights as backend/app/winners/scoring.py.
const CRITERIA = [
  ["Demand & trend", 20], ["Profitability", 20], ["Competition", 15], ["Creative potential", 10],
  ["Differentiation", 10], ["Logistics", 10], ["Market fit", 10], ["Risk", 5],
] as const;

const EXAMPLE_BREAKDOWN = { demand: 17, profitability: 16, competition: 11, creative: 9, differentiation: 7, logistics: 8, market_fit: 8, risk: 4 };

const STEPS = [
  { icon: RadarIcon, title: "We scan", desc: "Facebook Ad Library + TikTok, every night, per country." },
  { icon: Brain, title: "AI filters", desc: "Real products only. Duplicates merged, brands and risky items out." },
  { icon: Sparkles, title: "You get winners", desc: "5–10 scored picks every morning, with the proof behind each." },
];

const VS = [
  ["Time per day", "2–3 hours scrolling ads", "5 minutes"],
  ["How you choose", "Gut feeling", "Score out of 100 on 8 criteria"],
  ["Ad proof", "Screenshot hunting", "Days running, versions, stores"],
  ["Profit check", "Spreadsheet", "Built in, per product"],
  ["Ad ideas", "Copy competitors", "3–5 angles + hooks per product"],
] as const;

const PLANS = [
  { name: "Free", price: "$0", desc: "After your trial", cta: "Start free", highlight: false,
    features: ["Top 3 winners a day", "1 market", "Score + reasons", "Watchlist (10)"] },
  { name: "Starter", price: "$19.99", desc: "For one store", cta: "Start with Starter", highlight: false,
    features: ["All 5–10 winners daily", "1 market", "Ads & video proof", "3–5 ad angles per product", "5 AI reports a day", "7-day archive"] },
  { name: "Pro", price: "$69.99", desc: "For serious sellers", cta: "Start 7-day free trial", highlight: true,
    features: ["Everything in Starter", "All 3 markets", "Suppliers + Google Trends", "20 AI reports a day", "30-day archive + CSV", "Priority support"] },
  { name: "Agency", price: "$199", desc: "For teams & coaches", cta: "Contact us", highlight: false,
    features: ["Everything in Pro", "Every new market", "100 AI reports a day", "90-day archive", "Dedicated support"] },
];

const FAQ = [
  ["Do I need an account?", "No, not to look around. Today's #1 pick and the profit calculator on this page are free. A free account (Google, 10 seconds, no card) unlocks the full list, the ads, suppliers and AI research."],
  ["Do I need a credit card for the trial?", "No. You get 7 days of Pro free. After that you stay on the Free plan unless you choose a paid one."],
  ["Where does the data come from?", "The public Facebook Ad Library, TikTok and Google Trends — the same places pros check by hand, scanned for you every night."],
  ["Which countries?", "United States, United Kingdom and France today. Germany, Canada, Australia and the Gulf are next."],
  ["Can I cancel anytime?", "Yes, in one click from your billing page. You keep access until the end of the month you paid for."],
  ["I'm a dropshipping coach. Can I partner?", "Yes. You earn 30% of every payment for 12 months, and your students get 25% off their first month."],
] as const;

function Shot({ children, label }: { children: React.ReactNode; label: string }) {
  return (
    <div className="rounded-xl bg-zinc-950/70 border border-zinc-800 p-3 h-40 flex flex-col justify-center" aria-label={label}>
      {children}
    </div>
  );
}

const FEATURES = [
  {
    icon: BarChart3, title: "8-criteria score", desc: "See exactly why it scores high — and where it's weak.",
    visual: <Shot label="Example score radar"><CriteriaRadar breakdown={EXAMPLE_BREAKDOWN} size={140} compact /></Shot>,
  },
  {
    icon: Lightbulb, title: "Ad angles & hooks", desc: "3–5 ready-to-film angles for every product.",
    visual: (
      <Shot label="Example ad angles">
        {[["Problem → solution", "“I wasted $200 before finding this”"], ["Before / after", "“Watch what happens in 10 seconds”"], ["Gift idea", "“The gift she didn't know she needed”"]].map(([a, h]) => (
          <div key={a} className="text-[11px] py-1 border-b border-zinc-800 last:border-0">
            <span className="text-violet-300 font-semibold">{a}</span> <span className="text-zinc-400">{h}</span>
          </div>
        ))}
      </Shot>
    ),
  },
  {
    icon: TrendingUp, title: "Google Trends", desc: "Rising, stable or fading — before you spend.",
    visual: (
      <Shot label="Example search trend">
        <svg viewBox="0 0 200 80" className="w-full h-24" aria-hidden>
          <defs><linearGradient id="tg" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#8b5cf6" stopOpacity=".45" /><stop offset="1" stopColor="#8b5cf6" stopOpacity="0" /></linearGradient></defs>
          <path d="M0 70 L20 66 L40 68 L60 60 L80 62 L100 50 L120 44 L140 36 L160 24 L180 18 L200 8 L200 80 L0 80Z" fill="url(#tg)" />
          <path d="M0 70 L20 66 L40 68 L60 60 L80 62 L100 50 L120 44 L140 36 L160 24 L180 18 L200 8" fill="none" stroke="#a78bfa" strokeWidth="2.5" />
        </svg>
        <span className="text-[11px] text-emerald-300 font-semibold">▲ Rising · +140% in 90 days (example)</span>
      </Shot>
    ),
  },
  {
    icon: Calculator, title: "Profit calculator", desc: "Break-even ad cost and ROAS, per product.",
    visual: (
      <Shot label="Example profit numbers">
        <div className="grid grid-cols-2 gap-2 text-center">
          {[["Profit / order", "$9.40", "text-emerald-300"], ["Break-even ROAS", "1.6×", "text-white"], ["Max CPA", "$21.80", "text-white"], ["Margin", "62%", "text-emerald-300"]].map(([l, v, t]) => (
            <div key={l} className="bg-zinc-900 rounded-lg py-2"><div className="text-[10px] text-zinc-500">{l}</div><div className={`font-bold ${t}`}>{v}</div></div>
          ))}
        </div>
      </Shot>
    ),
  },
  {
    icon: FileSearch, title: "AI research report", desc: "12 sections, every claim linked to its source.",
    visual: (
      <Shot label="Example research report">
        {["Demand & trend", "Competitors & prices", "Target customer", "Risks & red flags", "Verdict: test it"].map((s, i) => (
          <div key={s} className="flex items-center gap-2 text-[11px] py-0.5">
            <Check size={12} className={i === 4 ? "text-violet-300" : "text-emerald-400"} />
            <span className={i === 4 ? "text-violet-200 font-semibold" : "text-zinc-300"}>{s}</span>
          </div>
        ))}
      </Shot>
    ),
  },
  {
    icon: GitCompare, title: "Compare products", desc: "Put picks side by side and choose in seconds.",
    visual: (
      <Shot label="Example comparison">
        {[["Product A", 84], ["Product B", 71], ["Product C", 58]].map(([n, s]) => (
          <div key={n} className="flex items-center gap-2 text-[11px] py-1">
            <span className="w-16 text-zinc-400">{n}</span>
            <div className="flex-1 h-2 bg-zinc-800 rounded-full"><div className="h-full rounded-full bg-violet-500" style={{ width: `${s}%` }} /></div>
            <span className="w-6 text-right text-white font-semibold tabular-nums">{s}</span>
          </div>
        ))}
      </Shot>
    ),
  },
];

export default async function LandingPage() {
  const preview = await getPreview();

  return (
    <div className="min-h-screen bg-zinc-950 text-white overflow-x-hidden">

      {/* Navbar */}
      <nav className="sticky top-0 z-50 bg-zinc-950/80 backdrop-blur-md border-b border-zinc-800/60">
        <div className="flex items-center justify-between px-4 sm:px-8 py-3.5 max-w-7xl mx-auto">
          <Link href="/" className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-600 to-indigo-600 flex items-center justify-center shadow-lg shadow-violet-900/40">
              <Zap size={16} className="text-white" />
            </div>
            <span className="font-bold text-white text-base sm:text-lg tracking-tight">ProductSpy</span>
            <span className="text-[10px] text-violet-400 font-bold bg-violet-500/10 border border-violet-500/20 px-1.5 py-0.5 rounded">PRO</span>
          </Link>
          <div className="hidden md:flex items-center gap-6">
            <a href="#live" className="text-zinc-400 hover:text-white text-sm">Today&apos;s picks</a>
            <a href="#features" className="text-zinc-400 hover:text-white text-sm">Features</a>
            <a href="#calculator" className="text-zinc-400 hover:text-white text-sm">Profit calculator</a>
            <a href="#pricing" className="text-zinc-400 hover:text-white text-sm">Pricing</a>
            <Link href="/login" className="text-zinc-400 hover:text-white text-sm">Sign in</Link>
            <Link href="/signup" className="bg-violet-600 hover:bg-violet-500 text-white text-sm font-semibold px-4 py-2 rounded-lg shadow-lg shadow-violet-900/30">
              Start free
            </Link>
          </div>
          <div className="md:hidden flex items-center gap-2">
            <Link href="/login" className="text-zinc-400 text-xs px-2 py-2">Sign in</Link>
            <Link href="/signup" className="inline-flex items-center min-h-[40px] bg-violet-600 text-white text-xs font-semibold px-3 rounded-lg">Start free</Link>
          </div>
        </div>
      </nav>

      <main>

      {/* Hero */}
      <section className="relative">
        <div aria-hidden className="pointer-events-none absolute inset-x-0 -top-24 h-[480px] bg-[radial-gradient(ellipse_at_top,rgba(139,92,246,0.25),transparent_60%)]" />
        <div className="relative max-w-4xl mx-auto px-4 sm:px-8 pt-14 sm:pt-20 pb-10 text-center space-y-6">
          <div className="inline-flex items-center gap-2 bg-violet-600/10 border border-violet-600/20 text-violet-300 text-xs font-semibold px-3 py-1.5 rounded-full">
            <Clock size={13} /> New winners every morning · US · UK · France
          </div>
          <h1 className="text-4xl sm:text-5xl md:text-6xl font-extrabold tracking-tight leading-[1.05]">
            Stop guessing.<br />
            <span className="bg-gradient-to-r from-violet-400 via-fuchsia-400 to-indigo-400 bg-clip-text text-transparent">Sell what&apos;s already winning.</span>
          </h1>
          <p className="text-zinc-400 text-base sm:text-lg max-w-2xl mx-auto">
            Every night we scan thousands of Facebook and TikTok ads. Every morning you get the 5–10 products advertisers are scaling — scored, with the proof.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
            <Link href="/signup" className="w-full sm:w-auto flex items-center justify-center gap-2 bg-violet-600 hover:bg-violet-500 text-white font-semibold px-7 py-3.5 rounded-xl shadow-lg shadow-violet-900/40">
              Start 7-day free trial <ArrowRight size={16} />
            </Link>
            <a href="#live" className="w-full sm:w-auto flex items-center justify-center gap-2 bg-zinc-900 hover:bg-zinc-800 text-zinc-200 font-semibold px-7 py-3.5 rounded-xl border border-zinc-700">
              See today&apos;s picks
            </a>
          </div>
          <p className="text-zinc-500 text-xs flex flex-wrap justify-center gap-x-4 gap-y-1">
            {["No credit card", "Sign up with Google in 10 s", "Cancel anytime"].map((t) => (
              <span key={t} className="inline-flex items-center gap-1"><Check size={12} className="text-emerald-400" /> {t}</span>
            ))}
          </p>
        </div>

        {/* Live picks */}
        <div id="live" className="relative max-w-6xl mx-auto px-4 sm:px-8 pb-16 scroll-mt-20">
          <div className="rounded-3xl border border-zinc-800 bg-zinc-900/40 p-3 sm:p-5 shadow-2xl shadow-violet-950/40">
            <LivePicks initial={preview} />
          </div>
        </div>
      </section>

      {/* Data sources / customers */}
      <TrustedBySection />

      {/* How it works */}
      <section className="max-w-5xl mx-auto px-4 sm:px-8 py-14">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 relative">
          {STEPS.map(({ icon: Icon, title, desc }, i) => (
            <div key={title} className="flex md:flex-col items-start md:items-center md:text-center gap-4 bg-zinc-900 border border-zinc-800 rounded-2xl p-5">
              <div className="relative w-14 h-14 rounded-2xl bg-gradient-to-br from-violet-600/30 to-indigo-600/20 border border-violet-500/30 flex items-center justify-center shrink-0">
                <Icon size={24} className="text-violet-300" />
                <span className="absolute -top-2 -right-2 w-6 h-6 rounded-full bg-violet-600 text-[11px] font-bold flex items-center justify-center">{i + 1}</span>
              </div>
              <div>
                <h3 className="text-white font-semibold">{title}</h3>
                <p className="text-zinc-400 text-sm mt-1">{desc}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Features bento */}
      <section id="features" className="max-w-6xl mx-auto px-4 sm:px-8 py-14 scroll-mt-20">
        <div className="text-center mb-10">
          <h2 className="text-2xl sm:text-4xl font-bold">Everything behind every pick</h2>
          <p className="text-zinc-500 text-sm mt-2">Not just a product name — the full case to test it (or skip it).</p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {FEATURES.map(({ icon: Icon, title, desc, visual }) => (
            <div key={title} className="bg-zinc-900 border border-zinc-800 hover:border-violet-500/40 rounded-2xl p-4 space-y-3 transition-colors">
              {visual}
              <div className="flex items-start gap-3">
                <div className="w-9 h-9 rounded-lg bg-violet-600/15 flex items-center justify-center shrink-0"><Icon size={17} className="text-violet-300" /></div>
                <div>
                  <h3 className="text-white font-semibold text-sm">{title}</h3>
                  <p className="text-zinc-400 text-xs mt-0.5">{desc}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
        <p className="text-center text-zinc-600 text-[11px] mt-4">Illustrations. Inside the app every number comes from real ads and data.</p>
      </section>

      {/* Score */}
      <section className="bg-zinc-900/40 border-y border-zinc-800/60 py-14">
        <div className="max-w-5xl mx-auto px-4 sm:px-8 grid md:grid-cols-2 gap-8 items-center">
          <div className="space-y-4">
            <h2 className="text-2xl sm:text-3xl font-bold">One honest score, 8 criteria</h2>
            <p className="text-zinc-400 text-sm">Missing data never counts as good news. Saturated products, brand copies and restricted items are removed before scoring.</p>
            <div className="flex items-center gap-2 text-xs text-zinc-400"><ShieldCheck size={15} className="text-emerald-400" /> Winners need 70+ and enough evidence.</div>
          </div>
          <div className="space-y-2">
            {CRITERIA.map(([label, pts]) => (
              <div key={label} className="flex items-center gap-3 text-sm">
                <span className="w-36 text-zinc-300 shrink-0">{label}</span>
                <div className="flex-1 h-2.5 bg-zinc-800 rounded-full overflow-hidden">
                  <div className="h-full rounded-full bg-gradient-to-r from-violet-600 to-fuchsia-500" style={{ width: `${(pts / 20) * 100}%` }} />
                </div>
                <span className="w-8 text-right text-violet-300 font-bold tabular-nums">{pts}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Free calculator */}
      <section id="calculator" className="max-w-4xl mx-auto px-4 sm:px-8 py-14 scroll-mt-20">
        <div className="text-center mb-8">
          <span className="inline-block text-[11px] font-bold text-emerald-300 bg-emerald-500/10 border border-emerald-500/20 rounded-full px-2.5 py-1 mb-3">FREE · NO SIGNUP</span>
          <h2 className="text-2xl sm:text-3xl font-bold">Will this product make you money?</h2>
          <p className="text-zinc-500 text-sm mt-2">Move the sliders. Know your break-even before you spend a dollar on ads.</p>
        </div>
        <MiniProfitCalc />
      </section>

      {/* vs manual */}
      <section className="max-w-4xl mx-auto px-4 sm:px-8 py-14">
        <h2 className="text-2xl sm:text-3xl font-bold text-center mb-8">Your mornings, before and after</h2>
        <div className="rounded-2xl border border-zinc-800 overflow-hidden text-sm">
          <div className="grid grid-cols-3 bg-zinc-900 text-xs font-semibold">
            <div className="p-3 text-zinc-500" />
            <div className="p-3 text-zinc-400 flex items-center gap-1"><X size={13} className="text-red-400" /> By hand</div>
            <div className="p-3 text-violet-300 flex items-center gap-1"><Zap size={13} /> ProductSpy</div>
          </div>
          {VS.map(([k, a, b]) => (
            <div key={k} className="grid grid-cols-3 border-t border-zinc-800">
              <div className="p-3 text-zinc-400 text-xs sm:text-sm">{k}</div>
              <div className="p-3 text-zinc-500 text-xs sm:text-sm">{a}</div>
              <div className="p-3 text-white text-xs sm:text-sm font-medium bg-violet-600/5">{b}</div>
            </div>
          ))}
        </div>
      </section>

      <ReviewsSection />

      {/* Pricing */}
      <section id="pricing" className="max-w-6xl mx-auto px-4 sm:px-8 py-14 scroll-mt-20">
        <div className="text-center mb-10">
          <h2 className="text-2xl sm:text-4xl font-bold">Less than one failed product test</h2>
          <p className="text-zinc-500 text-sm mt-2">Every account starts with 7 days of Pro, free. No card. Cancel anytime.</p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {PLANS.map((plan) => (
            <div key={plan.name} className={`relative rounded-2xl p-5 sm:p-6 space-y-5 border flex flex-col ${
              plan.highlight ? "bg-violet-600/10 border-violet-500/50 ring-1 ring-violet-500/30 shadow-xl shadow-violet-900/30" : "bg-zinc-900 border-zinc-800"
            }`}>
              {plan.highlight && <span className="absolute -top-3 left-1/2 -translate-x-1/2 bg-violet-600 text-white text-[11px] font-bold px-3 py-1 rounded-full">MOST POPULAR</span>}
              <div>
                <h3 className="text-white font-bold text-lg">{plan.name}</h3>
                <p className="text-zinc-500 text-sm">{plan.desc}</p>
              </div>
              <div>
                <span className="text-4xl font-extrabold text-white">{plan.price}</span>
                {plan.price !== "$0" && <span className="text-zinc-500 text-sm">/mo</span>}
              </div>
              <ul className="space-y-2.5 flex-1">
                {plan.features.map((f) => (
                  <li key={f} className="flex items-start gap-2 text-sm text-zinc-300"><Check size={14} className="text-emerald-400 shrink-0 mt-0.5" />{f}</li>
                ))}
              </ul>
              <Link href={plan.name === "Agency" ? "/contact" : "/signup"} className={`block text-center font-semibold py-2.5 rounded-xl text-sm ${
                plan.highlight ? "bg-violet-600 hover:bg-violet-500 text-white" : "bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700"
              }`}>{plan.cta}</Link>
            </div>
          ))}
        </div>
      </section>

      {/* Coaches */}
      <section className="max-w-5xl mx-auto px-4 sm:px-8 pb-14">
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-6 sm:p-8 flex flex-col md:flex-row items-center gap-6">
          <div className="w-14 h-14 rounded-2xl bg-amber-500/15 flex items-center justify-center shrink-0"><Handshake size={26} className="text-amber-300" /></div>
          <div className="flex-1 text-center md:text-left">
            <h3 className="text-white font-semibold text-lg">Dropshipping coach or community?</h3>
            <p className="text-zinc-400 text-sm mt-1">Earn <b className="text-white">30% for 12 months</b> on every student. They get <b className="text-white">25% off</b> their first month.</p>
          </div>
          <a href={`mailto:${SITE.supportEmail}?subject=ProductSpy%20partner%20program`}
             className="shrink-0 bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 text-white text-sm font-semibold px-5 py-2.5 rounded-xl">Become a partner</a>
        </div>
      </section>

      {/* FAQ */}
      <section className="max-w-3xl mx-auto px-4 sm:px-8 pb-14">
        <h2 className="text-2xl sm:text-3xl font-bold text-center mb-8">Questions</h2>
        <div className="space-y-2">
          {FAQ.map(([q, a]) => (
            <details key={q} className="group bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-3 open:border-zinc-700">
              <summary className="cursor-pointer list-none flex items-center justify-between gap-3 text-white font-medium text-sm">
                {q}<span className="text-zinc-500 group-open:rotate-45 transition-transform text-lg leading-none">+</span>
              </summary>
              <p className="text-zinc-400 text-sm mt-2">{a}</p>
            </details>
          ))}
        </div>
      </section>

      {/* Final CTA */}
      <section className="max-w-5xl mx-auto px-4 sm:px-8 pb-16">
        <div className="relative overflow-hidden bg-gradient-to-br from-violet-900/60 to-indigo-900/40 border border-violet-700/40 rounded-3xl p-8 sm:p-12 text-center space-y-5">
          <h2 className="text-2xl sm:text-4xl font-bold">Tomorrow morning, your first winners.</h2>
          <p className="text-zinc-300 text-sm sm:text-base">7 days of Pro free. No card. Takes 10 seconds.</p>
          <Link href="/signup" className="inline-flex items-center gap-2 bg-white text-zinc-950 hover:bg-zinc-200 font-bold px-8 py-3.5 rounded-xl">
            Start free <ArrowRight size={16} />
          </Link>
        </div>
      </section>

      </main>

      <SiteFooter />
    </div>
  );
}
