/**
 * API client — thin wrapper around fetch with auth headers.
 */
const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

async function getToken(): Promise<string | null> {
  if (typeof window === "undefined") return null;
  // Try Supabase session first
  try {
    const { createClient } = await import("@/lib/supabase/client");
    const supabase = createClient();
    const { data } = await supabase.auth.getSession();
    if (data.session?.access_token) return data.session.access_token;
  } catch {}
  // Fallback to localStorage
  return localStorage.getItem("access_token");
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = await getToken();

  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Unknown error" }));
    // FastAPI sends detail as a string, or — for plan locks — as
    // {error, message, upgrade_url}. Keep the code so pages can react to it.
    const detail = error.detail;
    const message =
      typeof detail === "string" ? detail : detail?.message || detail?.error || `HTTP ${res.status}`;
    const err = new Error(message) as Error & { status?: number; code?: string };
    err.status = res.status;
    err.code = typeof detail === "object" && detail ? detail.error : undefined;
    throw err;
  }

  return res.json();
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};

// ---- Typed API calls ----

/** A saved product. Mirrors schemas.WatchedProduct. */
export interface WatchedProduct {
  id: string;
  title: string;
  image_url: string | null;
  price_usd: number | null;
  cost_usd: number | null;
  /** Best Daily Winners score in the last 7 days, and the market it was in. */
  score: number | null;
  market: string | null;
}

export interface WatchlistItem {
  id: string;
  product: WatchedProduct;
  added_at: string;
}

export const watchlistApi = {
  list: () => api.get<{ items: WatchlistItem[] }>("/watchlist/"),
  add: (productId: string) => api.post(`/watchlist/${productId}`),
  remove: (productId: string) => api.delete(`/watchlist/${productId}`),
};

export const billingApi = {
  checkout: (plan: string, provider: "stripe" | "paypal" = "stripe") =>
    api.post<{ checkout_url: string; provider: string }>(`/billing/checkout?plan=${plan}&provider=${provider}`),
  portal: () => api.post<{ portal_url: string }>("/billing/portal"),
  cancel: () => api.post<{ message: string }>("/billing/cancel"),
  startTrial: () => api.post<{ message: string; trial: TrialInfo }>("/billing/trial"),
  status: () => api.get<{
    plan: string; status: string; provider: string;
    current_period_end: string | null; can_manage: boolean; trial: TrialInfo | null;
  }>("/billing/status"),
};

/** Mirrors schemas.Trial. */
export interface TrialInfo {
  active: boolean;
  plan: string;
  ends_at: string | null;
  days_left: number;
  hours_left: number;
  used: boolean;
  expired: boolean;
  eligible: boolean;
  length_days: number;
}

export interface Me {
  id: string;
  email: string;
  name: string;
  avatar_url: string | null;
  subscription: { plan: string; status: string; current_period_end: string | null };
  trial?: TrialInfo | null;
}

export const usersApi = {
  me: () => api.get<Me>("/users/me"),
};

// ---- Daily Winners ----

export interface Market {
  code: string;
  name: string;
  flag: string;
  currency: string;
  meta_official_api: boolean;
}

export interface WinnersEntitlements {
  plan: string;
  markets: number;
  winners_per_day: number;
  history_days: number;
  ad_evidence: boolean;
  export_csv: boolean;
}

export interface Breakdown {
  scaling: number;
  engagement: number;
  demand: number;
  margin: number;
  freshness: number;
}

export interface Penalty { points: number; reason: string }

export interface WinnerPick {
  rank: number;
  tier: "winner" | "rising" | "watch";
  total: number;
  /** Beyond the plan's daily allowance: rank and score only. */
  locked: boolean;
  breakdown?: Breakdown;
  reasons?: string[];
  penalties?: Penalty[];
  confidence?: "low" | "medium" | "high" | null;
  product?: {
    id: string;
    title: string;
    image_url: string | null;
    category: string | null;
    price_usd: number | null;
    cost_usd: number | null;
    /** Cost is an AI estimate, not a supplier listing. */
    cost_estimated: boolean;
    margin_pct: number | null;
  };
  stats?: {
    days_running: number | null;
    creatives: number | null;
    new_creatives_7d: number | null;
    stores: number | null;
    videos: number | null;
    views: number | null;
    engagement_rate: number | null;
    intent_ratio: number | null;
    ctr: number | null;
    sources: string[];
  };
  links?: { store_url: string | null; ad_url: string | null; supplier_url: string | null };
}

export interface WinnersResponse {
  market: string;
  date: string | null;
  winners: WinnerPick[];
  locked_count: number;
  plan: string;
  message?: string;
}

export interface AdEvidence {
  platform: string;
  advertiser_name: string | null;
  ad_text: string | null;
  landing_url: string | null;
  landing_domain: string | null;
  thumbnail_url: string | null;
  ad_url: string | null;
  started_at: string | null;
  days_running: number | null;
  variant_count: number | null;
  reach: number | null;
  views: number | null;
  likes: number | null;
  comments: number | null;
  shares: number | null;
  ctr: number | null;
}

export interface ProductEvidence {
  market: string;
  product: {
    id: string; title: string; image_url: string | null; category: string | null;
    price_usd: number | null; cost_usd: number | null; cost_estimated: boolean;
    margin_pct: number | null; product_url: string | null; first_seen_at: string | null;
    attributes: Record<string, unknown>;
  };
  score: {
    scored_on: string; total: number; breakdown: Breakdown; reasons: string[];
    penalties: Penalty[]; confidence: string | null; excluded: string | null;
  } | null;
  history: { date: string; total: number }[];
  suppliers: { platform: string; supplier_name: string; supplier_url: string; unit_cost_usd: number | null }[];
  ads: Record<string, AdEvidence[]>;
  ad_counts: Record<string, number>;
  ad_evidence_locked: boolean;
}

export interface WinnerRun {
  market: string;
  started_at: string;
  finished_at: string | null;
  status: "running" | "ok" | "partial" | "failed";
  stats: Record<string, number>;
  /** First error of the run (e.g. no ads collected), or null. */
  problem: string | null;
}

export const winnersApi = {
  markets: () =>
    api.get<{
      markets: Market[];
      following: string[];
      entitlements: WinnersEntitlements;
      plans: Record<string, WinnersEntitlements>;
    }>("/winners/markets"),
  setMarkets: (markets: string[]) =>
    api.post<{ markets: string[]; max_markets: number }>("/winners/preferences", { markets }),
  list: (market: string, date?: string) =>
    api.get<WinnersResponse>(`/winners?market=${market}${date ? `&date=${date}` : ""}`),
  dates: (market: string) =>
    api.get<{ market: string; history_days: number; dates: { date: string; winners: number; total: number }[] }>(
      `/winners/dates?market=${market}`
    ),
  status: () => api.get<{ runs: WinnerRun[] }>("/winners/status"),
  product: (id: string, market: string) =>
    api.get<ProductEvidence>(`/winners/products/${id}?market=${market}`),
  /** Downloads the CSV with the auth header (a plain link can't send it). */
  exportCsv: async (market: string, date?: string) => {
    const token = await getToken();
    const res = await fetch(`${BASE_URL}/winners/export.csv?market=${market}${date ? `&date=${date}` : ""}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error("CSV export is on the Pro and Agency plans.");
    const url = URL.createObjectURL(await res.blob());
    const a = document.createElement("a");
    a.href = url;
    a.download = `winners-${market}-${date ?? "latest"}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  },
};

// ---- Quote requests (/quotes) ----

export interface Quote {
  id: string;
  user_email: string;
  product_id: string | null;
  product_title: string;
  quantity: number;
  destination_country: string;
  target_price_usd: number | null;
  notes: string;
  status: "open" | "quoted" | "closed";
  quoted_unit_usd: number | null;
  quoted_shipping_usd: number | null;
  reply: string;
  created_at: string;
  replied_at: string | null;
}

export interface QuoteCreate {
  product_id: string;
  quantity: number;
  destination_country: string;
  target_price_usd?: number | null;
  notes?: string;
}

export const quotesApi = {
  create: (body: QuoteCreate) => api.post<Quote>("/quotes/", body),
  list: (all = false) => api.get<{ quotes: Quote[]; is_admin: boolean }>(`/quotes/${all ? "?all=true" : ""}`),
  reply: (id: string, body: {
    status: "quoted" | "closed";
    quoted_unit_usd?: number | null;
    quoted_shipping_usd?: number | null;
    reply?: string;
  }) => api.post<Quote>(`/quotes/${id}/reply`, body),
};
