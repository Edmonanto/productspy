"use client";

import { useEffect, useState } from "react";

interface Props {
  src: string | null | undefined;
  alt: string;
  className?: string;
  /** Rendered when there is no URL, or the image cannot be loaded at all. */
  fallback: React.ReactNode;
}

/** Roughly the widest a product image is ever drawn in this UI. */
const THUMB_PX = 480;

/**
 * Ask the source CDN for a thumbnail instead of the master image.
 *
 * Catalogue images are enormous — TikTok serves up to 4320x4320 and 1688
 * around 800-1920 — while the largest we ever draw is a ~260px card. Both
 * CDNs encode the size in the URL, so the small version costs one string
 * edit. Anything that doesn't match a known pattern is returned untouched.
 */
export function thumbnail(url: string, px: number = THUMB_PX): string {
  try {
    const { host } = new URL(url);
    if (host.endsWith("ttcdn-us.com") || host.endsWith("tiktokcdn.com")) {
      // ...~tplv-<template>-crop-webp:4320:4320.webp
      return url.replace(/:(\d+):(\d+)\.webp/, `:${px}:${px}.webp`);
    }
    if (host.endsWith("alicdn.com")) {
      // alicdn appends the size to the filename: <name>.jpg_480x480.jpg
      return /\.(jpe?g|png)$/i.test(new URL(url).pathname)
        ? `${url}_${px}x${px}.jpg`
        : url;
    }
  } catch {
    // Not a URL we can parse — hand it back and let the browser decide.
  }
  return url;
}

/**
 * A product photo from a supplier CDN.
 *
 * Three things every call site needs and none of them had:
 *
 * `referrerPolicy="no-referrer"` — 1688 images live on cbu01.alicdn.com,
 * which refuses requests carrying our referrer. Measured on the live page:
 * the default policy fails, no-referrer returns the image.
 *
 * A thumbnail request, because drawing a 4320x4320 master in a 260px card
 * wastes bandwidth and tens of megabytes of decoded memory per image, forty
 * at a time on Trending.
 *
 * An error fallback, because the call sites only handled a *missing* URL. A
 * URL that failed to load left the browser rendering alt text, which for a
 * 1688 listing is a wall of untranslated Chinese sprawling out of the card.
 *
 * A failed thumbnail retries the original URL before giving up, so a CDN
 * whose pattern we guessed wrong costs a second request rather than the
 * picture.
 *
 * Deliberately NOT lazy-loaded. `loading="lazy"` defers the fetch until the
 * browser considers the image visible, and in a backgrounded tab that never
 * happens — measured on the deployed page, 0 of 40 images began loading over
 * 48 seconds, and flipping them to eager loaded every one immediately.
 */
export default function ProductImage({ src, alt, className, fallback }: Props) {
  const [stage, setStage] = useState<"thumb" | "original" | "failed">("thumb");

  useEffect(() => setStage("thumb"), [src]);

  if (!src || stage === "failed") return <>{fallback}</>;

  const url = stage === "thumb" ? thumbnail(src) : src;

  return (
    <img
      key={stage}
      src={url}
      alt={alt}
      className={className}
      referrerPolicy="no-referrer"
      onError={() => setStage(stage === "thumb" && url !== src ? "original" : "failed")}
    />
  );
}
