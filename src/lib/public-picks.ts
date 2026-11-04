/** Server-side fetchers for the public "winning products" pages (no login). */
import type { Breakdown } from "@/lib/api";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
const REVALIDATE = 1800;

export interface PublicPick {
  date: string; product_id: string; title: string; image_url: string | null; category: string | null;
  price_usd: number | null; total: number; tier: string; trend: string;
  stores: number | null; days_running: number | null; breakdown: Breakdown; reasons: string[];
  angle: { angle: string; hook: string } | null;
}

async function get<T>(path: string): Promise<T | null> {
  try {
    const r = await fetch(`${API}${path}`, { next: { revalidate: REVALIDATE }, signal: AbortSignal.timeout(8000) });
    return r.ok ? ((await r.json()) as T) : null;
  } catch {
    return null;
  }
}

export const getPublicTop = (market: string) =>
  get<{ market: string; days: number; picks: PublicPick[] }>(`/winners/public/top?market=${market}`);

export const getPublicProduct = (id: string, market: string) =>
  get<{ market: string; pick: PublicPick; featured_on: string[] }>(
    `/winners/public/products/${encodeURIComponent(id)}?market=${market}`);
