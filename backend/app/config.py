"""Runtime configuration, read from the environment."""
import os

# ── Core ────────────────────────────────────────────────────────────────────
DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Supabase JWT verification. Supabase signs access tokens with this shared
# secret (Project Settings -> API -> JWT Secret) using HS256.
SUPABASE_JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
JWT_AUDIENCE = "authenticated"

# Comma-separated list of origins allowed to call this API.
CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "CORS_ORIGINS", "http://localhost:3000,https://productspy.pro"
    ).split(",")
    if o.strip()
]

API_PREFIX = "/api/v1"

# ── Plans ───────────────────────────────────────────────────────────────────
# Mirrors the PLANS array in src/app/dashboard/billing/page.tsx.
UNLIMITED = "unlimited"

PLAN_SEARCH_LIMITS: dict[str, int | str] = {
    "free": 5,
    "starter": 50,
    "pro": UNLIMITED,
    "agency": UNLIMITED,
}

PLAN_WATCHLIST_LIMITS: dict[str, int | str] = {
    "free": 10,
    "starter": UNLIMITED,
    "pro": UNLIMITED,
    "agency": UNLIMITED,
}

DEFAULT_PLAN = "free"

# ── Ingestion ───────────────────────────────────────────────────────────────
INGEST_LIMIT = int(os.environ.get("INGEST_LIMIT", "50"))

# How far back trend scoring looks for a comparison snapshot. Until history
# reaches this far, trend stays neutral rather than guessed.
TREND_WINDOW_DAYS = int(os.environ.get("TREND_WINDOW_DAYS", "7"))

# AliExpress Affiliate / Dropshipping API (apply via AliExpress Portals).
ALIEXPRESS_APP_KEY = os.environ.get("ALIEXPRESS_APP_KEY", "")
ALIEXPRESS_APP_SECRET = os.environ.get("ALIEXPRESS_APP_SECRET", "")
ALIEXPRESS_TRACKING_ID = os.environ.get("ALIEXPRESS_TRACKING_ID", "productspy")
ALIEXPRESS_CATEGORY_IDS = os.environ.get("ALIEXPRESS_CATEGORY_IDS", "")

# 1688 Open Platform (Alibaba domestic wholesale — real factory costs).
# namespace/api_name are configurable: which call you may invoke depends on
# the service package granted to your app.
ALIBABA1688_APP_KEY = os.environ.get("ALIBABA1688_APP_KEY", "")
ALIBABA1688_APP_SECRET = os.environ.get("ALIBABA1688_APP_SECRET", "")
ALIBABA1688_ACCESS_TOKEN = os.environ.get("ALIBABA1688_ACCESS_TOKEN", "")
ALIBABA1688_NAMESPACE = os.environ.get(
    "ALIBABA1688_NAMESPACE", "com.alibaba.fenxiao.crossborder"
)
ALIBABA1688_API_NAME = os.environ.get(
    "ALIBABA1688_API_NAME", "product.search.keywordQuery"
)
ALIBABA1688_KEYWORDS = os.environ.get("ALIBABA1688_KEYWORDS", "")
ALIBABA1688_CATEGORY_ID = os.environ.get("ALIBABA1688_CATEGORY_ID", "")

# 1688 via third-party aggregator (works without Open Platform approval).
# NOTE: these endpoints are plain HTTP on bare IPs, so the token and the
# response travel unencrypted. Keep the tokens in env, never in code.
AGG1688_SEARCH_URL = os.environ.get("AGG1688_SEARCH_URL", "")
AGG1688_SEARCH_TOKEN = os.environ.get("AGG1688_SEARCH_TOKEN", "")
AGG1688_DETAIL_URL = os.environ.get("AGG1688_DETAIL_URL", "")
AGG1688_DETAIL_TOKEN = os.environ.get("AGG1688_DETAIL_TOKEN", "")
# Search terms define the catalogue — one search call returns ~60 offers.
AGG1688_KEYWORDS = os.environ.get("AGG1688_KEYWORDS", "")
# Detail is one call per product, so enrichment is capped. 0 disables it.
AGG1688_ENRICH_TOP = int(os.environ.get("AGG1688_ENRICH_TOP", "0"))
# P4P results are paid placement, not organic demand.
AGG1688_INCLUDE_ADS = os.environ.get("AGG1688_INCLUDE_ADS", "").lower() == "true"
AGG1688_TIMEOUT = int(os.environ.get("AGG1688_TIMEOUT", "60"))


def agg1688_keywords() -> list[str]:
    return [k.strip() for k in AGG1688_KEYWORDS.split(",") if k.strip()]


# TikTok Shop via jhzyapi aggregator. The strongest demand/trend source, and
# the only one here reporting a real USD retail price. Each response reports
# charged_yuan/balance_yuan, which the provider logs.
TIKTOK_API_BASE = os.environ.get(
    "TIKTOK_API_BASE", "https://jhzyapi.com/api/tiktok/v1/shop"
)
TIKTOK_TOKEN = os.environ.get("TIKTOK_TOKEN", "")
# Search terms define the catalogue; one call returns ~30 products.
TIKTOK_KEYWORDS = os.environ.get("TIKTOK_KEYWORDS", "")
# Optional: pull a specific seller's catalogue (same payload shape as search).
TIKTOK_SELLER_IDS = os.environ.get("TIKTOK_SELLER_IDS", "")
# Detail is one call per product, so enrichment is capped. 0 disables it.
TIKTOK_ENRICH_TOP = int(os.environ.get("TIKTOK_ENRICH_TOP", "0"))
TIKTOK_TIMEOUT = int(os.environ.get("TIKTOK_TIMEOUT", "60"))


def tiktok_keywords() -> list[str]:
    return [k.strip() for k in TIKTOK_KEYWORDS.split(",") if k.strip()]


def tiktok_seller_ids() -> list[str]:
    return [s.strip() for s in TIKTOK_SELLER_IDS.split(",") if s.strip()]


# Amazon via jhzyapi, across marketplaces. The retail price anchor: 1688
# gives cost with no retail, Amazon gives retail with no cost.
AMAZON_API_BASE = os.environ.get(
    "AMAZON_API_BASE", "https://jhzyapi.com/api/amazon/v1"
)
AMAZON_TOKEN = os.environ.get("AMAZON_TOKEN", "")
AMAZON_KEYWORDS = os.environ.get("AMAZON_KEYWORDS", "")
AMAZON_SITES = os.environ.get("AMAZON_SITES", "US")
AMAZON_TIMEOUT = int(os.environ.get("AMAZON_TIMEOUT", "60"))

# FX to USD. Non-USD marketplaces are priced in their own currency, and an
# unconverted price is worse than none — margin would read 229 EUR as 229 USD.
USD_PER_GBP = float(os.environ.get("USD_PER_GBP", "1.27"))
USD_PER_EUR = float(os.environ.get("USD_PER_EUR", "1.08"))
USD_PER_CAD = float(os.environ.get("USD_PER_CAD", "0.73"))
USD_PER_AUD = float(os.environ.get("USD_PER_AUD", "0.66"))


def amazon_keywords() -> list[str]:
    return [k.strip() for k in AMAZON_KEYWORDS.split(",") if k.strip()]


def amazon_sites() -> list[str]:
    return [s.strip().upper() for s in AMAZON_SITES.split(",") if s.strip()]


def usd_rates() -> dict[str, float]:
    """Multiplier from each currency to USD. Unlisted -> price dropped."""
    return {
        "USD": 1.0,
        "GBP": USD_PER_GBP,
        "EUR": USD_PER_EUR,
        "CAD": USD_PER_CAD,
        "AUD": USD_PER_AUD,
    }


# 1688 quotes wholesale CNY. Converting to USD and deriving an indicative
# retail price keeps margin scoring meaningful on wholesale-only listings.
CNY_PER_USD = float(os.environ.get("CNY_PER_USD", "7.15"))
WHOLESALE_MARKUP = float(os.environ.get("WHOLESALE_MARKUP", "3.0"))


# ── Claude (ai_summary) ─────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-5")

# ── Matching (cross-platform) ───────────────────────────────────────────────
# Stage 2 is retail x suppliers, so both sides are capped: comparing whole
# catalogues is quadratic and floods the review queue with weak pairs.
MATCH_TRANSLATE_LIMIT = int(os.environ.get("MATCH_TRANSLATE_LIMIT", "120"))
MATCH_RETAIL_LIMIT = int(os.environ.get("MATCH_RETAIL_LIMIT", "50"))
MATCH_SUPPLIER_LIMIT = int(os.environ.get("MATCH_SUPPLIER_LIMIT", "300"))

# ── Billing ─────────────────────────────────────────────────────────────────
# Where the provider sends the customer back after checkout.
APP_URL = os.environ.get("APP_URL", "https://productspy.pro")

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

PAYPAL_CLIENT_ID = os.environ.get("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = os.environ.get("PAYPAL_CLIENT_SECRET", "")
PAYPAL_WEBHOOK_ID = os.environ.get("PAYPAL_WEBHOOK_ID", "")
PAYPAL_API_BASE = os.environ.get(
    "PAYPAL_API_BASE", "https://api-m.paypal.com"  # sandbox: api-m.sandbox.paypal.com
)

# Paid plans only — "free" is never checked out.
STRIPE_PRICE_IDS: dict[str, str] = {
    "starter": os.environ.get("STRIPE_PRICE_STARTER", ""),
    "pro": os.environ.get("STRIPE_PRICE_PRO", ""),
    "agency": os.environ.get("STRIPE_PRICE_AGENCY", ""),
}

PAYPAL_PLAN_IDS: dict[str, str] = {
    "starter": os.environ.get("PAYPAL_PLAN_STARTER", ""),
    "pro": os.environ.get("PAYPAL_PLAN_PRO", ""),
    "agency": os.environ.get("PAYPAL_PLAN_AGENCY", ""),
}

PAID_PLANS = ("starter", "pro", "agency")
