import type { CriterionKey } from "@/lib/utils";
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
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PUT", body: JSON.stringify(body) }),
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
  category?: string | null;
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

/** Points per criterion; null = no data (left out of the score). */
export type Breakdown = Partial<Record<CriterionKey, number | null>>;

export interface EvidenceItem { text: string; kind: "observed" | "calculated" | "ai" | "assumption" }

export interface Criterion {
  score: number | null;
  max: number;
  known: boolean;
  coverage: number;
  evidence: EvidenceItem[];
}

/** A suggested ad angle (written daily for each pick). */
export interface AdAngle { angle: string; hook: string; format?: string; audience?: string }

export interface PickEconomics {
  complete: boolean;
  contribution_before_ads_usd: number | null;
  contribution_margin_pct: number | null;
  break_even_roas: number | null;
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
  band?: string;
  trend?: string;
  trend_why?: string | null;
  strengths?: string[];
  weaknesses?: string[];
  missing?: string[];
  scored_on?: string | null;
  economics?: PickEconomics;
  angles?: AdAngle[];
  /** Google Trends in this market: status + last 26 weekly points (relative 0-100 index). */
  search_trend?: { status: string; growth: number | null; term: string | null; geo: string | null; series: number[] } | null;
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
    angles?: AdAngle[];
  };
  score: {
    scored_on: string; total: number; breakdown: Breakdown; reasons: string[];
    penalties: Penalty[]; confidence: string | null; excluded: string | null;
    band: string; criteria: Partial<Record<CriterionKey, Criterion>>;
    trend: string; trend_why: string | null; strengths: string[]; weaknesses: string[];
    missing: string[]; known_points: number | null;
    signals: Record<string, number | number[] | null>;
  } | null;
  criteria_labels?: Record<string, string>;
  /** Google Trends for this market (relative 0-100 weekly index, not volume). */
  search_trend?: {
    term: string; geo: string; at: string; status: string; growth: number | null; level: number | null;
    series: { date: string; value: number }[];
  } | null;
  assumptions?: Record<string, number>;
  history: { date: string; total: number; paid_ads?: number; videos?: number }[];
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
  /** Daily winners email on/off. */
  digest: () => api.get<{ on: boolean }>("/winners/digest"),
  setDigest: (on: boolean) => api.post<{ on: boolean }>("/winners/digest", { on }),
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

// ---- Research: AI report, validation workflow, comparison (/research) ----

export type FindingType = "fact" | "calculated" | "estimate" | "hypothesis";

export interface AIReport {
  product_name: string;
  category: string;
  description: string;
  target_audience: string[];
  primary_problem: string;
  demand_summary: string;
  competition_summary: string;
  commercial_potential: string;
  criteria_comments: Partial<Record<CriterionKey, string>>;
  key_findings: { text: string; type: FindingType; sources: string[] }[];
  risks: { area: string; description: string; severity: "low" | "medium" | "high" }[];
  suggested_price_range: { low: number; high: number; basis: string } | null;
  offer_ideas: string[];
  bundle_ideas: string[];
  creative_angles: { angle: string; hook: string; format: string }[];
  personas: { name: string; description: string; pain_points: string[] }[];
  ugc_script: string;
  product_page_headlines: string[];
  competitor_insights: { doing_well: string[]; gaps: string[]; differentiation: string[]; unverified_claims: string[] };
  market_adaptation: { suggestion: string; basis: "evidence" | "hypothesis" }[];
  next_validation_steps: string[];
  missing_data: string[];
  recommendation: { verdict: "validate_now" | "investigate_further" | "monitor" | "pass"; rationale: string };
}

export interface CompetitorPage {
  domain: string; url: string; title: string; price: number | null; currency: string | null;
  price_usd: number | null; description: string; offer_cues: string[];
}

export interface ResearchReport {
  id: string;
  status: "pending" | "ready" | "failed";
  report: {
    ai: AIReport;
    sources: { id: string; kind: string; label: string; url: string | null }[];
    competitors: CompetitorPage[];
    evidence_summary: { ads: number; competitor_pages: number; suppliers: number };
    not_available: string[];
    generated_at: string;
  } | null;
  warnings: string[];
  model?: string | null;
  error?: string | null;
  created_at: string;
  finished_at?: string | null;
}

export type StepStatus = "not_started" | "in_progress" | "completed" | "blocked";

export interface ValidationStep {
  stage: string; label: string; status: StepStatus; notes: string; links: string[]; updated_at: string | null;
}

export interface ValidationResults {
  supplier_quote_usd?: number | null; shipping_quote_usd?: number | null; selling_price_usd?: number | null;
  ad_spend_usd?: number | null; orders?: number | null; revenue_usd?: number | null; refunds?: number | null;
  decision?: "launch" | "iterate" | "drop" | null;
}

export interface Validation {
  product_id: string;
  steps: ValidationStep[];
  progress: { completed: number; total: number };
  results: ValidationResults;
  comparison: { planned: Record<string, unknown>; actual: Record<string, number>; notes: string[] } | null;
}

export interface CompareItem {
  id: string; title: string; image_url: string | null; category: string | null;
  price_usd: number | null; cost_usd: number | null; cost_estimated: boolean;
  score: number | null; confidence: string | null; scored_on: string | null;
  breakdown: Breakdown; trend: string | null; band: string | null;
  stores: number | null; videos: number | null; weaknesses: string[]; excluded: string | null;
  economics: { complete: boolean; contribution_before_ads_usd: number | null; contribution_margin_pct: number | null;
               break_even_roas: number | null; break_even_cpa_usd: number | null };
}

export const researchApi = {
  report: (id: string, market: string) =>
    api.get<{ market: string; report: ResearchReport | null; quota: { used: number; limit: number } }>(
      `/research/${id}/report?market=${market}`),
  generate: (id: string, market: string, refresh = false) =>
    api.post<{ market: string; report: ResearchReport; cached: boolean }>(
      `/research/${id}/report?market=${market}${refresh ? "&refresh=true" : ""}`),
  validation: (id: string) => api.get<Validation>(`/research/${id}/validation`),
  setStep: (id: string, stage: string, body: { status: StepStatus; notes: string; links: string[] }) =>
    api.put<{ stage: string; status: StepStatus }>(`/research/${id}/validation/${stage}`, body),
  setResults: (id: string, body: ValidationResults) =>
    api.put<{ results: ValidationResults; comparison: Validation["comparison"] }>(`/research/${id}/results`, body),
  compare: (ids: string[], market: string) =>
    api.get<{ market: string; items: CompareItem[]; max: number; criteria: { key: CriterionKey; label: string; max: number }[] }>(
      `/research/compare?ids=${ids.map(encodeURIComponent).join(",")}&market=${market}`),
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

// ---- Partner / coach referral program (/partners) ----

export interface PartnerStats {
  signups: number; customers: number; active: number;
  on_hold: number; payable: number; paid: number; revenue: number;
}

export interface PartnerMe {
  is_admin: boolean;
  referred_by: { partner: string; discount_pct: number; discount_used: boolean } | null;
  partner: {
    name: string; code: string; link: string; status: "active" | "paused";
    commission_pct: number; commission_months: number; discount_pct: number;
    payout_method: "paypal" | "wise" | "bank" | "other" | null; payout_details: string;
    clicks: number; hold_days: number; stats: PartnerStats;
    monthly: { month: string; earned: number; payments: number }[];
    recent: { id: string; amount: number; commission: number; currency: string;
              status: "on_hold" | "payable" | "paid" | "void"; created_at: string; paid_at: string | null }[];
  } | null;
}

export interface AdminPartner {
  id: string; name: string; email: string; code: string; link: string; status: "active" | "paused";
  commission_pct: number; commission_months: number; discount_pct: number; clicks: number;
  payout_method: string | null; payout_details: string; linked: boolean; stats: PartnerStats;
}

export interface Payout {
  affiliate_id: string; name: string; email: string; payout_method: string | null; payout_details: string;
  currency: string; total: number; payments: number; oldest: string;
}

export const partnersApi = {
  offer: (code: string) =>
    api.get<{ valid: boolean; code?: string; partner?: string; discount_pct?: number }>(`/partners/offer?code=${encodeURIComponent(code)}`),
  click: (code: string) => api.post<{ ok: boolean }>("/partners/click", { code }),
  attribute: (code: string) => api.post<{ ok: boolean; reason: string }>("/partners/attribute", { code }),
  me: () => api.get<PartnerMe>("/partners/me"),
  setPayout: (method: string, details: string) => api.put<{ message: string }>("/partners/me/payout", { method, details }),
  adminList: () => api.get<{ partners: AdminPartner[]; hold_days: number }>("/partners/admin"),
  adminCreate: (body: { name: string; email: string; code: string; commission_pct?: number; commission_months?: number; discount_pct?: number }) =>
    api.post<{ id: string; code: string; link: string }>("/partners/admin", body),
  adminUpdate: (id: string, body: Partial<Pick<AdminPartner, "status" | "commission_pct" | "commission_months" | "discount_pct">>) =>
    request<{ message: string }>(`/partners/admin/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  payouts: () => api.get<{ payouts: Payout[] }>("/partners/admin/payouts"),
  markPaid: (affiliate_id: string, payout_ref: string) =>
    api.post<{ marked_paid: number }>("/partners/admin/payouts", { affiliate_id, payout_ref }),
};
