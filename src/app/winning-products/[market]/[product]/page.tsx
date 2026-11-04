import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, ArrowRight, Lightbulb } from "lucide-react";
import PublicShell from "@/components/public/PublicShell";
import { CriteriaRadar, ProductVisual, TrendIcon } from "@/components/visual/Visuals";
import { LANDING_COPY } from "@/content/landing-copy";
import { idFromSlug, marketBySlug, productSlug } from "@/content/seo-markets";
import { getPublicProduct } from "@/lib/public-picks";
import { SITE } from "@/lib/site";
import { category, fmtDate, price } from "@/lib/public-format";

export const revalidate = 1800;

type Params = { params: { market: string; product: string } };

async function load({ params }: Params) {
  const m = marketBySlug(params.market);
  const id = idFromSlug(params.product);
  if (!m || !id) return null;
  const data = await getPublicProduct(id, m.code);
  return data ? { m, ...data } : null;
}

export async function generateMetadata(props: Params): Promise<Metadata> {
  const d = await load(props);
  if (!d) return { robots: { index: false } };
  const url = `/winning-products/${d.m.slug}/${productSlug(d.pick.title, d.pick.product_id)}`;
  const title = d.m.t.productTitle(d.pick.title);
  const description = d.m.t.productDesc(d.pick.title, d.pick.total);
  return {
    title, description, alternates: { canonical: url },
    openGraph: { type: "article", url, siteName: SITE.name, title, description,
                 ...(d.pick.image_url ? { images: [d.pick.image_url] } : {}) },
  };
}

export default async function PublicProductPage(props: Params) {
  const d = await load(props);
  if (!d) notFound();
  const { m, pick: p, featured_on } = d;
  const hub = `/winning-products/${m.slug}`;
  const signup = `/signup${m.lang === "en" ? "" : `?lang=${m.lang}`}`;
  const L = LANDING_COPY[m.lang];

  const jsonLd = {
    "@context": "https://schema.org", "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "ProductSpy Pro", item: `${SITE.url}${L.home === "/" ? "" : L.home}` },
      { "@type": "ListItem", position: 2, name: m.t.h1, item: `${SITE.url}${hub}` },
      { "@type": "ListItem", position: 3, name: p.title },
    ],
  };

  return (
    <PublicShell lang={m.lang}>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <Link href={hub} className="inline-flex items-center gap-1.5 text-sm text-zinc-400 hover:text-white mb-6">
        <ArrowLeft size={14} /> {m.t.seeAll}
      </Link>

      <div className="grid md:grid-cols-2 gap-6 mb-10">
        <ProductVisual src={p.image_url} alt={p.title} category={p.category} iconSize={64} className="w-full aspect-square rounded-2xl border border-zinc-800" />
        <div className="space-y-4">
          <p className="text-violet-300 text-xs font-semibold">{m.flag} {m.t.featured} {featured_on.map((x) => fmtDate(m, x)).join(", ")}</p>
          <h1 className="text-2xl sm:text-4xl font-extrabold tracking-tight leading-tight">{p.title}</h1>
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-lg bg-emerald-500 text-emerald-950 px-2.5 py-1 text-lg font-extrabold tabular-nums">{p.total}<span className="text-xs font-bold">/100</span></span>
            <TrendIcon trend={p.trend} withLabel labels={m.lang === "en" ? undefined : L.trend} />
            {price(m, p.price_usd) && <span className="bg-zinc-800 rounded-full px-2.5 py-1 text-xs">{price(m, p.price_usd)}</span>}
            {p.category && <span className="bg-zinc-800 rounded-full px-2.5 py-1 text-xs">{category(m, p.category)}</span>}
          </div>
          <ul className="text-sm text-zinc-300 space-y-1">
            {!!p.stores && <li>• {m.t.stores(p.stores)}</li>}
            {!!p.days_running && <li>• {m.t.daysAds(p.days_running)}</li>}
            {/* Score reasons are written in English by the engine: shown on English pages only. */}
            {m.lang === "en" && p.reasons.map((r) => <li key={r}>• {r}</li>)}
          </ul>
          {p.angle && (
            <div className="bg-violet-500/10 border border-violet-500/20 rounded-xl p-3 text-sm">
              <div className="flex items-center gap-1.5 text-violet-300 font-semibold"><Lightbulb size={14} /> {m.t.angle}: {p.angle.angle}</div>
              <div className="text-zinc-300 mt-1">“{p.angle.hook}”</div>
            </div>
          )}
        </div>
      </div>

      {Object.keys(p.breakdown).length > 0 && (
        <section className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5 mb-10">
          <h2 className="font-semibold mb-2">{m.t.productH2}</h2>
          <CriteriaRadar breakdown={p.breakdown} size={260} labels={L.radar} />
        </section>
      )}

      <section data-track="seo_product" className="bg-gradient-to-br from-violet-900/60 to-indigo-900/40 border border-violet-700/40 rounded-2xl p-6 sm:p-8 text-center space-y-3">
        <h2 className="font-bold text-xl sm:text-2xl">{m.t.ctaTitle}</h2>
        <p className="text-sm text-zinc-300 max-w-xl mx-auto">{m.t.ctaBody}</p>
        <Link href={signup} className="inline-flex items-center gap-2 bg-white text-zinc-950 hover:bg-zinc-200 font-bold px-6 py-3 rounded-xl text-sm">
          {m.t.cta} <ArrowRight size={15} />
        </Link>
      </section>
    </PublicShell>
  );
}
