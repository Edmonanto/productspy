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

# 1688 quotes wholesale CNY. Converting to USD and deriving an indicative
# retail price keeps margin scoring meaningful on wholesale-only listings.
CNY_PER_USD = float(os.environ.get("CNY_PER_USD", "7.15"))
WHOLESALE_MARKUP = float(os.environ.get("WHOLESALE_MARKUP", "3.0"))

# Apify — one actor per source; leave an actor id unset to skip that source.
APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "")
# Verified to exist in the Apify store, ~19k runs/30d, and its example run
# input is the {queries, maxResults, category, country} shape we send.
APIFY_ALIEXPRESS_ACTOR = os.environ.get(
    "APIFY_ALIEXPRESS_ACTOR", "thirdwatch/aliexpress-product-scraper"
)

# Search terms the actor crawls. Without these it returns nothing, so this is
# effectively what defines your catalogue.
APIFY_QUERIES = os.environ.get(
    "APIFY_QUERIES",
    "pet accessories,phone accessories,kitchen gadgets,home decor,fitness",
)
APIFY_CATEGORY = os.environ.get("APIFY_CATEGORY", "all")
APIFY_COUNTRY = os.environ.get("APIFY_COUNTRY", "US")
# Escape hatch: raw JSON replacing the built input for a differently-shaped actor.
APIFY_INPUT_JSON = os.environ.get("APIFY_INPUT_JSON", "")


def apify_queries() -> list[str]:
    return [q.strip() for q in APIFY_QUERIES.split(",") if q.strip()]

APIFY_AMAZON_ACTOR = os.environ.get("APIFY_AMAZON_ACTOR", "")
APIFY_TIKTOK_ACTOR = os.environ.get("APIFY_TIKTOK_ACTOR", "")
APIFY_ADS_ACTOR = os.environ.get("APIFY_ADS_ACTOR", "")
APIFY_TIMEOUT_SECONDS = int(os.environ.get("APIFY_TIMEOUT_SECONDS", "300"))

# ── Claude (ai_summary) ─────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-5")

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
