/**
 * Public "winning products" pages, one per launched market (see
 * app/winning-products). France is written in French ("tu"), the others in
 * English. Only the free #1 pick of each day is shown — never the paid list.
 */
import type { Lang } from "@/content/landing-copy";

export interface MarketPage {
  slug: string; code: string; lang: Lang; flag: string;
  country: string;          // as used in a sentence
  t: {
    h1: string; sub: string; metaTitle: string; metaDesc: string;
    today: string; previous: string; categories: string; how: string; howBody: string;
    ctaTitle: string; ctaBody: string; cta: string; empty: string; score: string;
    stores: (n: number) => string; daysAds: (n: number) => string; featured: string;
    productTitle: (title: string) => string; productDesc: (title: string, score: number) => string;
    productH2: string; why: string; angle: string; seeAll: string; otherMarkets: string;
    breadcrumb: string; locale: string;
  };
}

const en = (country: string, inCountry: string) => ({
  h1: `Winning products in ${country}`,
  sub: `The free #1 pick of every day, chosen from real Facebook and TikTok ads running ${inCountry}. Updated every morning.`,
  metaTitle: `Winning products in ${country} today — dropshipping picks | ProductSpy Pro`,
  metaDesc: `Today's #1 winning product ${inCountry} and every previous daily #1, picked from real Facebook and TikTok ads and scored on 8 criteria. Updated every morning.`,
  today: "Today's #1 pick", previous: "Previous #1 picks", categories: "Top categories, last 60 days",
  how: "How these are picked",
  howBody: `Every night ProductSpy scans the Facebook Ad Library and TikTok ${inCountry}, merges duplicates, removes brands and risky items, and scores each product out of 100 on demand, profit, competition, creatives, offer, logistics, market fit and risk. The highest-scoring product each day is shown here for free.`,
  ctaTitle: "Want the whole list?",
  ctaBody: "Each morning has 5–10 winners, with the ads, stores, suppliers and profit behind each one. Try Pro free for 7 days, no card.",
  cta: "Start free", empty: "No picks yet for this market — the first daily scan hasn't finished.",
  score: "Score",
  stores: (n: number) => `${n} stores advertising`, daysAds: (n: number) => `${n} days of ads`,
  featured: "#1 on",
  productTitle: (title: string) => `${title} — winning product ${inCountry} | ProductSpy Pro`,
  productDesc: (title: string, score: number) => `${title} was the #1 winning product ${inCountry} on ProductSpy, scoring ${score}/100 from real Facebook and TikTok ads. See its score, trend and ad angle.`,
  productH2: "Score breakdown", why: "Why it scored high", angle: "Ad angle to test",
  seeAll: `All winning products in ${country}`, otherMarkets: "Other markets", breadcrumb: "Winning products",
  locale: "en-US",
});

export const MARKET_PAGES: MarketPage[] = [
  { slug: "united-states", code: "US", lang: "en", flag: "🇺🇸", country: "the United States", t: en("the United States", "in the US") },
  { slug: "united-kingdom", code: "UK", lang: "en", flag: "🇬🇧", country: "the United Kingdom", t: en("the United Kingdom", "in the UK") },
  {
    slug: "france", code: "FR", lang: "fr", flag: "🇫🇷", country: "France",
    t: {
      h1: "Produits gagnants en France",
      sub: "Le produit n°1 gratuit de chaque jour, choisi à partir de vraies pubs Facebook et TikTok diffusées en France. Mis à jour chaque matin.",
      metaTitle: "Produits gagnants en France aujourd'hui — dropshipping | ProductSpy Pro",
      metaDesc: "Le produit gagnant n°1 du jour en France et tous les n°1 précédents, repérés dans de vraies pubs Facebook et TikTok et notés sur 8 critères. Mis à jour chaque matin.",
      today: "Le produit n°1 du jour", previous: "Les n°1 précédents", categories: "Catégories en tête, 60 derniers jours",
      how: "Comment ils sont choisis",
      howBody: "Chaque nuit, ProductSpy analyse la Bibliothèque publicitaire Facebook et TikTok en France, fusionne les doublons, écarte les marques et les produits à risque, puis note chaque produit sur 100 : demande, marge, concurrence, créas, offre, logistique, adéquation au marché et risque. Le produit le mieux noté de chaque jour est affiché ici gratuitement.",
      ctaTitle: "Tu veux la liste complète ?",
      ctaBody: "Chaque matin, 5 à 10 produits gagnants, avec les pubs, les boutiques, les fournisseurs et la marge derrière chacun. Essaie Pro gratuitement pendant 7 jours, sans carte.",
      cta: "Commencer gratuitement", empty: "Pas encore de produits pour ce marché — la première analyse n'est pas terminée.",
      score: "Note",
      stores: (n: number) => `${n} boutiques en pub`, daysAds: (n: number) => `${n} jours de pub`,
      featured: "N°1 le",
      productTitle: (title: string) => `${title} — produit gagnant en France | ProductSpy Pro`,
      productDesc: (title: string, score: number) => `${title} a été le produit gagnant n°1 en France sur ProductSpy, avec une note de ${score}/100 à partir de vraies pubs Facebook et TikTok. Découvre sa note, sa tendance et son angle pub.`,
      productH2: "Détail de la note", why: "Pourquoi cette note", angle: "Angle pub à tester",
      seeAll: "Tous les produits gagnants en France", otherMarkets: "Autres marchés", breadcrumb: "Produits gagnants",
      locale: "fr-FR",
    },
  },
];

export const marketBySlug = (slug: string) => MARKET_PAGES.find((m) => m.slug === slug);

export function productSlug(title: string, id: string) {
  const s = title.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase()
    .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 60).replace(/-+$/, "");
  return `${s || "product"}-${id}`;
}

/** The product id is the last 36 characters (a UUID) of the slug. */
export function idFromSlug(slug: string) {
  const id = slug.slice(-36);
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id) ? id : null;
}
