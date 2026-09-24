"use client";

import { useState } from "react";

interface Props {
  src: string | null | undefined;
  alt: string;
  className?: string;
  /** Rendered when there is no URL, or the image fails to load. */
  fallback: React.ReactNode;
}

/**
 * A product photo from a supplier CDN.
 *
 * Two things every call site needs and none of them had:
 *
 * `referrerPolicy="no-referrer"` — 1688 images live on cbu01.alicdn.com,
 * which refuses requests carrying our referrer. Measured from the live page:
 * the default policy fails, no-referrer returns the 800x800 image. That was
 * every 1688 product on the dashboard, a third of the catalogue, showing a
 * broken image.
 *
 * An `onError` fallback — the plain `<img>` only handled a *missing* URL, so
 * a URL that failed to load left the browser rendering alt text, which for a
 * 1688 listing is a wall of untranslated Chinese sprawling out of the card.
 */
export default function ProductImage({ src, alt, className, fallback }: Props) {
  const [failed, setFailed] = useState(false);

  if (!src || failed) return <>{fallback}</>;

  return (
    <img
      src={src}
      alt={alt}
      className={className}
      referrerPolicy="no-referrer"
      loading="lazy"
      onError={() => setFailed(true)}
    />
  );
}
