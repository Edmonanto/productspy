"use client";

import Image from "next/image";
import { useEffect, useState } from "react";

interface Props {
  src: string | null | undefined;
  alt: string;
  className?: string;
  /** Rendered when there is no URL, or the image cannot be loaded. */
  fallback: React.ReactNode;
}

/** Widest a product image is ever drawn in this UI, give or take. */
const RENDER_PX = 480;

/**
 * A product photo, served from our own origin.
 *
 * Earlier versions pointed the browser straight at the supplier CDNs and
 * tried to out-argue them from the client: no-referrer to satisfy alicdn's
 * hotlink rules, a guessed thumbnail URL per CDN to avoid shipping a
 * 4320x4320 master into a 260px card, and a timer to give up on a request
 * that never resolved. On desktop that worked. On an iPhone it did not: 1688
 * images errored outright and TikTok images hung without ever firing an
 * error, so cards showed an icon or nothing at all.
 *
 * Every one of those is a symptom of asking the viewer's device to fetch
 * from a CDN it may not reach on terms we cannot control. next/image moves
 * that fetch to the server: it pulls the original once, resizes it, caches
 * it, and serves the result from this domain. The phone only has to reach
 * us.
 *
 * That also deletes the parts that were guesses — no referrer policy to get
 * right, no per-CDN URL pattern to infer, no timeout heuristic — and caps
 * the decode cost, since what arrives is already the size it is drawn at.
 * Hosts must be listed in next.config.mjs `images.remotePatterns`.
 */
export default function ProductImage({ src, alt, className, fallback }: Props) {
  const [failed, setFailed] = useState(false);

  useEffect(() => setFailed(false), [src]);

  if (!src || failed) return <>{fallback}</>;

  return (
    <Image
      src={src}
      alt={alt}
      width={RENDER_PX}
      height={RENDER_PX}
      sizes="(max-width: 640px) 50vw, 300px"
      className={className}
      onError={() => setFailed(true)}
    />
  );
}
