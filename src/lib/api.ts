/**
 * API client — thin wrapper around fetch with auth headers.
 */
const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;

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
    throw new Error(error.detail || `HTTP ${res.status}`);
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

export interface Product {
  id: string;
  title: string;
  image_url: string | null;
  product_url: string;
  category: string | null;
  price_usd: number | null;
  cost_usd: number | null;
  source: string;
  score: {
    overall_score: number;
    demand_score: number;
    margin_score: number;
    competition_score: number;
    trend_score: number;
    ai_summary: string;
  } | null;
  suppliers: Supplier[];
  ad_signals: AdSignal[];
}

export interface Supplier {
  platform: string;
  supplier_name: string;
  supplier_url: string;
  unit_cost_usd: number;
  shipping_days: number;
  rating: number;
}

export interface AdSignal {
  platform: string;
  ad_count: number;
  last_seen_at: string;
}

export interface WatchlistItem {
  id: string;
  product: Product;
  added_at: string;
}

export const productsApi = {
  trending: (params: Record<string, string | number> = {}) => {
    const qs = new URLSearchParams(params as Record<string, string>).toString();
    return api.get<{ products: Product[]; total: number }>(`/products/trending?${qs}`);
  },
  search: (q: string, minScore = 40) =>
    api.get<{ products: Product[]; total: number }>(`/products/search?q=${encodeURIComponent(q)}&min_score=${minScore}`),
  detail: (id: string) => api.get<Product>(`/products/${id}`),
  rescore: (id: string) => api.post<{ score: Product["score"] }>(`/products/${id}/rescore`),
};

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
  status: () => api.get<{
    plan: string; status: string; provider: string;
    current_period_end: string | null; search_quota: number; can_manage: boolean;
  }>("/billing/status"),
};

export interface Me {
  id: string;
  email: string;
  name: string;
  avatar_url: string | null;
  subscription: { plan: string; status: string; current_period_end: string | null };
  quota: { plan: string; limit: number | string; used: number; remaining: number | string };
}

export const usersApi = {
  me: () => api.get<Me>("/users/me"),
};
