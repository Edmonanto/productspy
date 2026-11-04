import type { MetadataRoute } from "next";
import { SITE } from "@/lib/site";

export default function sitemap(): MetadataRoute.Sitemap {
  const pages: [string, number][] = [["", 1], ["/fr", 1], ["/signup", 0.8], ["/login", 0.5], ["/contact", 0.4],
    ["/privacy", 0.2], ["/terms", 0.2]];
  return pages.map(([path, priority]) => ({
    url: `${SITE.url}${path}`,
    lastModified: new Date(),
    changeFrequency: path === "" || path === "/fr" ? "weekly" : "monthly",
    priority,
    ...(path === "" || path === "/fr"
      ? { alternates: { languages: { en: `${SITE.url}/`, fr: `${SITE.url}/fr` } } }
      : {}),
  }));
}
