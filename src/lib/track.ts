/**
 * Anonymous landing-page events for the signup funnel (backend app/funnel.py).
 * No cookie, no id: just the event, the page language and which button.
 * Sent with sendBeacon as text/plain so it survives navigating away (the
 * click that triggers it usually leaves the page) and needs no CORS preflight.
 */
const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export type LandingEvent = "landing_view" | "signup_click";

export function track(event: LandingEvent, data: { lang: string; source?: string }) {
  try {
    const body = JSON.stringify({ event, ...data });
    const blob = new Blob([body], { type: "text/plain" });
    if (navigator.sendBeacon?.(`${API}/events`, blob)) return;
    void fetch(`${API}/events`, { method: "POST", body, headers: { "Content-Type": "text/plain" }, keepalive: true });
  } catch {
    /* analytics must never break the page */
  }
}
