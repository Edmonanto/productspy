/**
 * Social proof shown on the landing page.
 *
 * ONLY add real entries here: a review must come from a real ProductSpy user
 * who agreed to be quoted, and a "trusted by" store must have agreed to be
 * listed. Invented reviews or logos of companies that aren't customers are
 * misleading (and against FTC rules in the US / consumer law in the EU).
 *
 * While a list is empty, its section shows an honest fallback instead:
 *   - no reviews      -> an "early access" invite
 *   - no trusted-by   -> the public data sources ProductSpy reads
 */

export type Review = {
  name: string;          // as the user agreed to be shown, e.g. "Sarah K."
  role: string;          // e.g. "Shopify store owner"
  market?: string;       // e.g. "🇦🇺 Australia"
  quote: string;         // their words, unedited apart from length
  rating: 1 | 2 | 3 | 4 | 5;
  date: string;          // ISO date the review was given, e.g. "2026-11-02"
  avatarUrl?: string;    // optional, must be allowed in image-hosts.mjs
};

export type TrustedBy = {
  name: string;          // store / agency name
  url?: string;          // their site
  logoUrl?: string;      // optional logo (they must have agreed)
};

export const REVIEWS: Review[] = [
  // {
  //   name: "First L.",
  //   role: "Shopify store owner",
  //   market: "🇺🇸 United States",
  //   quote: "Their exact words…",
  //   rating: 5,
  //   date: "2026-11-01",
  // },
];

export const TRUSTED_BY: TrustedBy[] = [
  // { name: "Store Name", url: "https://example-store.com" },
];

/** Public sources the scan reads — shown while TRUSTED_BY is empty. */
export const DATA_SOURCES = [
  { name: "Facebook Ad Library", desc: "Ads running in your market" },
  { name: "TikTok Creative Center", desc: "Top-performing TikTok ads" },
  { name: "TikTok", desc: "Product videos and comments" },
  { name: "AliExpress", desc: "Supplier costs" },
];
