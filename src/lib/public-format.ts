import type { MarketPage } from "@/content/seo-markets";

/** "$29.90" in English, "29,90 $" in French (prices are USD). */
export function price(m: MarketPage, usd: number | null) {
  if (usd == null) return null;
  return m.lang === "fr" ? `${usd.toFixed(2).replace(".", ",")} $` : `$${usd.toFixed(2)}`;
}

const CATEGORY_FR: Record<string, string> = {
  home: "Maison", kitchen: "Cuisine", beauty: "Beauté", health: "Santé", fitness: "Sport", pets: "Animaux",
  baby: "Bébé", "kids-toys": "Jouets", "fashion-accessories": "Accessoires de mode", fashion: "Mode",
  "tech-gadgets": "High-tech", car: "Auto", outdoor: "Plein air", tools: "Outils",
};

/** Category label for display: French on French pages, else "kids toys" → "Kids toys". */
export function category(m: MarketPage, c: string) {
  if (m.lang === "fr" && CATEGORY_FR[c]) return CATEGORY_FR[c];
  const s = c.replace(/-/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function fmtDate(m: MarketPage, iso: string, long = false) {
  return new Date(iso + "T00:00:00").toLocaleDateString(m.t.locale,
    long ? { weekday: "long", day: "numeric", month: "long", year: "numeric" } : { day: "numeric", month: "short" });
}
