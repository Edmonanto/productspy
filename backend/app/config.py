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

# Apify — one actor per source; leave an actor id unset to skip that source.
APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "")
APIFY_AMAZON_ACTOR = os.environ.get("APIFY_AMAZON_ACTOR", "")
APIFY_TIKTOK_ACTOR = os.environ.get("APIFY_TIKTOK_ACTOR", "")
APIFY_ADS_ACTOR = os.environ.get("APIFY_ADS_ACTOR", "")
APIFY_TIMEOUT_SECONDS = int(os.environ.get("APIFY_TIMEOUT_SECONDS", "300"))

# ── Claude (ai_summary) ─────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-5")
