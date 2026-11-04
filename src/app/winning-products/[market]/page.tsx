import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowRight, Clock, Store } from "lucide-react";
import PublicShell from "@/components/public/PublicShell";
import { CriteriaRadar, ProductVisual, TrendIcon } from "@/components/visual/Visuals";
import { LANDING_COPY } from "@/content/landing-copy";
import { MARKET_PAGES, marketBySlug, productSlug, type MarketPage } from "@/content/seo-markets";
import { getPublicTop, type PublicPick } from "@/lib/public-picks";
import { category, fmtDate, price } from "@/lib/public-format";
import { SITE } from "@/lib/site";

export const revalidate = 1800;

export function generateStaticParams() {
  return MARKET_PAGES.map((m) => ({ market: m.slug }));
}

export function generateMetadata({ params }: { params: { market: string } }): Metadata {
  const m = marketBySlug(params.market);
  if (!m) return {};
  const url = `/winning-products/${m.slug}`;
  return {
    title: m.t.metaTitle, description: m.t.metaDesc, alternates: { canonical: url },
    openGraph: { type: "website", url, siteName: SITE.name, title: m.t.metaTitle, description: m.t.metaDesc,
                 locale: m.lang === "fr" ? "fr_FR" : "en_US" },
  };
}

function Stats({ m, p }: { m: MarketPage; p: PublicPick }) {
  const trend = m.lang === "en" ? undefined : LANDING_COPY[m.lang].trend;
  return (
    <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-zinc-300">
      <TrendIcon trend={p.trend} withLabel labels={trend} />
      {price(m, p.price_usd) && <span className="bg-zinc-800 rounded-full px-2 py-0.5">{price(m, p.price_usd)}</span>}
      {!!p.stores && <span className="bg-zinc-800 rounded-full px-2 py-0.5 inline-flex items-center gap-1"><Store size={11} /> {m.t.stores(p.stores)}</span>}
      {!!p.days_running && <span className="bg-zinc-800 rounded-full px-2 py-0.5 inline-flex items-center gap-1"><Clock size={11} /> {m.t.daysAds(p.days_running)}</span>}
    </div>
  );
}

export default async function MarketWinnersPage({ params }: { params: { market: string } }) {
  const m = marketBySlug(params.market);
  if (!m) notFound();
  const data = await getPublicTop(m.code);
  const picks = data?.picks ?? [];
  const [today, ...previous] = picks;
  const href = (p: PublicPick) => `/winning-products/${m.slug}/${productSlug(p.title, p.product_id)}`;
  const signup = `/signup${m.lang === "en" ? "" : `?lang=${m.lang}`}`;
  const radar = LANDING_COPY[m.lang].radar;

  const cats = Object.entries(picks.reduce<Record<string, number>>((acc, p) => {
    if (p.category) acc[p.category] = (acc[p.category] ?? 0) + 1;
    return acc;
  }, {})).sort((a, b) => b[1] - a[1]).slice(0, 6);

  const jsonLd = {
    "@context": "https://schema.org", "@type": "ItemList", name: m.t.h1,
    itemListElement: picks.slice(0, 30).map((p, i) => ({
      "@type": "ListItem", position: i + 1, name: p.title, url: `${SITE.url}${href(p)}`,
    })),
  };

  return (
    <PublicShell lang={m.lang}>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <header className="max-w-3xl space-y-3 mb-8">
        <p className="text-violet-300 text-xs font-semibold">{m.flag} {m.t.breadcrumb}</p>
        <h1 className="text-3xl sm:text-5xl font-extrabold tracking-tight">{m.t.h1}</h1>
        <p className="text-zinc-400 text-base sm:text-lg">{m.t.sub}</p>
      </header>

      {!today ? (
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-8 text-center text-sm text-zinc-400">{m.t.empty}</div>
      ) : (
        <>
          <section className="mb-12">
            <h2 className="text-lg font-semibold mb-3">{m.t.today} · <span className="text-zinc-400 font-normal">{fmtDate(m, today.date, true)}</span></h2>
            <Link href={href(today)} className="group grid md:grid-cols-[1.2fr_1fr] bg-zinc-900 border border-violet-500/40 hover:border-violet-400 rounded-2xl overflow-hidden transition-colors">
              <ProductVisual src={today.image_url} alt={today.title} category={today.category} iconSize={56} className="w-full aspect-[16/10] md:aspect-auto md:min-h-[300px]" />
              <div className="p-5 space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <h3 className="text-xl font-bold leading-snug group-hover:text-violet-200">{today.title}</h3>
                  <span className="shrink-0 rounded-lg bg-emerald-500 text-emerald-950 px-2.5 py-1 text-lg font-extrabold tabular-nums" title={`${m.t.score} ${today.total}/100`}>{today.total}</span>
                </div>
                <Stats m={m} p={today} />
                {Object.keys(today.breakdown).length > 0 && <CriteriaRadar breakdown={today.breakdown} size={180} labels={radar} />}
              </div>
            </Link>
          </section>

          {previous.length > 0 && (
            <section className="mb-12">
              <h2 className="text-lg font-semibold mb-3">{m.t.previous}</h2>
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
                {previous.map((p) => (
                  <Link key={p.date} href={href(p)} className="group bg-zinc-900 border border-zinc-800 hover:border-violet-500/50 rounded-xl overflow-hidden transition-colors">
                    <div className="relative">
                      <ProductVisual src={p.image_url} alt={p.title} category={p.category} className="w-full aspect-square" />
                      <span className="absolute top-2 right-2 rounded-lg bg-black/60 backdrop-blur px-2 py-0.5 text-sm font-extrabold tabular-nums">{p.total}</span>
                      <span className="absolute bottom-2 left-2 rounded-md bg-black/60 backdrop-blur px-1.5 py-0.5 text-[11px] text-zinc-200">{m.t.featured} {fmtDate(m, p.date)}</span>
                    </div>
                    <div className="px-3 py-2.5">
                      <div className="text-sm font-medium line-clamp-2 group-hover:text-white text-zinc-100">{p.title}</div>
                      {p.category && <div className="text-xs text-zinc-500 mt-0.5">{category(m, p.category)}</div>}
                    </div>
                  </Link>
                ))}
              </div>
            </section>
          )}

          {cats.length > 0 && (
            <section className="mb-12">
              <h2 className="text-lg font-semibold mb-3">{m.t.categories}</h2>
              <div className="flex flex-wrap gap-2">
                {cats.map(([c, n]) => (
                  <span key={c} className="bg-zinc-900 border border-zinc-800 rounded-full px-3 py-1.5 text-sm text-zinc-300">
                    {category(m, c)} <span className="text-zinc-500">· {n}</span>
                  </span>
                ))}
              </div>
            </section>
          )}
        </>
      )}

      <section className="grid md:grid-cols-2 gap-4 mb-10">
        <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6">
          <h2 className="font-semibold mb-2">{m.t.how}</h2>
          <p className="text-sm text-zinc-400 leading-relaxed">{m.t.howBody}</p>
        </div>
        <div data-track="seo_market" className="bg-gradient-to-br from-violet-900/60 to-indigo-900/40 border border-violet-700/40 rounded-2xl p-6 space-y-3">
          <h2 className="font-semibold text-lg">{m.t.ctaTitle}</h2>
          <p className="text-sm text-zinc-300">{m.t.ctaBody}</p>
          <Link href={signup} className="inline-flex items-center gap-2 bg-white text-zinc-950 hover:bg-zinc-200 font-bold px-5 py-2.5 rounded-xl text-sm">
            {m.t.cta} <ArrowRight size={15} />
          </Link>
        </div>
      </section>

      <nav className="text-sm text-zinc-500 flex flex-wrap gap-x-4 gap-y-1">
        <span>{m.t.otherMarkets}:</span>
        {MARKET_PAGES.filter((o) => o.slug !== m.slug).map((o) => (
          <Link key={o.slug} href={`/winning-products/${o.slug}`} className="text-zinc-300 hover:text-white">{o.flag} {o.t.h1}</Link>
        ))}
      </nav>
    </PublicShell>
  );
}
