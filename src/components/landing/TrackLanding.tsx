"use client";

import { useEffect } from "react";
import { track } from "@/lib/track";

/** Records one landing_view, and a signup_click for any link to /signup.
 *  The button's place on the page comes from the nearest [data-track]. */
export default function TrackLanding({ lang }: { lang: string }) {
  useEffect(() => {
    track("landing_view", { lang });
    const onClick = (e: MouseEvent) => {
      const a = (e.target as Element | null)?.closest?.('a[href^="/signup"]');
      if (!a) return;
      const source = a.closest("[data-track]")?.getAttribute("data-track") ?? "other";
      track("signup_click", { lang, source });
    };
    document.addEventListener("click", onClick, true);
    return () => document.removeEventListener("click", onClick, true);
  }, [lang]);
  return null;
}
