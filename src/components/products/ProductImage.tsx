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
/** How long a thumbnail gets before we stop trusting it and try the master. */
const THUMB_TIMEOUT_MS = 4000;

export default function ProductImage({ src, alt, className, fallback }: Props) {
  const [stage, setStage] = useState<"thumb" | "original" | "failed">("thumb");
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    setStage("thumb");
    setLoaded(false);
  }, [src]);

  const url = !src ? "" : stage === "thumb" ? thumbnail(src) : src;
  const rewritten = stage === "thumb" && url !== src;

  // A thumbnail URL is a pattern we inferred, not one the CDN promised. If it
  // fails loudly, onError moves on. If it fails *quietly* — a decode the
  // browser abandons, a response that never resolves — nothing fires and the
  // card would sit empty forever. WebKit in particular can drop an image
  // without reporting an error, and that is not reproducible from a desktop
  // Chrome, so this does not rely on catching it: an unloaded thumbnail is
  // abandoned on a timer and the original master URL is used instead.
  useEffect(() => {
    if (!src || !rewritten || loaded) return;
    const timer = setTimeout(() => {
      setStage((s) => (s === "thumb" ? "original" : s));
    }, THUMB_TIMEOUT_MS);
    return () => clearTimeout(timer);
  }, [src, rewritten, loaded]);

  if (!src || stage === "failed") return <>{fallback}</>;

  return (
    <img
      key={stage}
      src={url}
      alt={alt}
      className={className}
      referrerPolicy="no-referrer"
      onLoad={() => setLoaded(true)}
      onError={() => setStage(rewritten ? "original" : "failed")}
    />
  );
}
