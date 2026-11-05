import type { MetadataRoute } from "next";
import { MARKET_PAGES, productSlug } from "@/content/seo-markets";
import { getPublicTop } from "@/lib/public-picks";
import { SITE } from "@/lib/site";

export const revalidate = 3600;

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const pages: [string, number][] = [["", 1], ["/fr", 1], ["/signup", 0.8], ["/login", 0.5], ["/contact", 0.4],
    ["/privacy", 0.2], ["/terms", 0.2]];
  const base: MetadataRoute.Sitemap = pages.map(([path, priority]) => ({
    url: `${SITE.url}${path}`,
    lastModified: new Date(),
    changeFrequency: path === "" || path === "/fr" ? "weekly" : "monthly",
    priority,
    ...(path === "" || path === "/fr"
      ? { alternates: { languages: { en: `${SITE.url}/`, fr: `${SITE.url}/fr` } } }
      : {}),
  }));

  // Public "winning products" pages: one hub per market (changes daily) and
  // one page per recent free #1 pick. If the API is down, the hubs still list.
  const markets = await Promise.all(MARKET_PAGES.map(async (m) => ({ m, data: await getPublicTop(m.code) })));
  const seo: MetadataRoute.Sitemap = markets.flatMap(({ m, data }) => {
    const picks = data?.picks ?? [];
    const seen = new Set<string>();
    return [
      { url: `${SITE.url}/winning-products/${m.slug}`, lastModified: picks[0] ? new Date(picks[0].date) : new Date(),
        changeFrequency: "daily" as const, priority: 0.9 },
      ...picks.filter((p) => !seen.has(p.product_id) && seen.add(p.product_id)).map((p) => ({
        url: `${SITE.url}/winning-products/${m.slug}/${productSlug(p.title, p.product_id)}`,
        lastModified: new Date(p.date), changeFrequency: "weekly" as const, priority: 0.6,
      })),
    ];
  });
  return [...base, ...seo];
}
