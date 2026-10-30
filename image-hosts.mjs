/**
 * Image hosts next/image may fetch from. Shared by next.config.mjs (the
 * optimizer's allowlist) and ProductImage (which skips anything else, rather
 * than letting next/image throw on an unlisted host — Daily Winners images can
 * come from any store's own domain).
 */
export const IMAGE_HOSTS = [
  // Product photos stored by our own API (backend app/winners/photos.py).
  "productspy-api.onrender.com",
  // AliExpress supplier listings.
  "**.aliexpress.com",
  "**.alicdn.com",
  "**.tiktokcdn.com",
  // TikTok Shop product images (linked from videos) come from ttcdn-us.com.
  "**.ttcdn-us.com",
  // Ad creatives, TikTok video covers, store product photos.
  "**.fbcdn.net",
  "**.tiktokcdn-us.com",
  "**.tiktokcdn-eu.com",
  "**.ibyteimg.com",
  "**.byteimg.com",
  "cdn.shopify.com",
];
