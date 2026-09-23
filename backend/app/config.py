"""Runtime configuration, read from the environment."""
import os

from dotenv import load_dotenv

load_dotenv()

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

# ── 1688 data provider ──────────────────────────────────────────────────────
# 1688 is the only product source. Search and item detail are two separate
# hosted endpoints, each with its own metered token — keep both out of git.
ALI1688_SEARCH_URL = os.environ.get(
    "ALI1688_SEARCH_URL", "http://175.178.149.181:5432/1688_keyword_search-pc"
)
ALI1688_SEARCH_TOKEN = os.environ.get("ALI1688_SEARCH_TOKEN", "")
ALI1688_DETAIL_URL = os.environ.get(
    "ALI1688_DETAIL_URL", "http://114.132.60.246:8010/1688_item_detail_info"
)
ALI1688_DETAIL_TOKEN = os.environ.get("ALI1688_DETAIL_TOKEN", "")
ALI1688_TIMEOUT_SECONDS = float(os.environ.get("ALI1688_TIMEOUT_SECONDS", "30"))

# Tokens are billed per call, so results are cached in Postgres. A repeated
# keyword/page inside the TTL, or a detail refresh inside its TTL, costs nothing.
SEARCH_CACHE_TTL_HOURS = float(os.environ.get("SEARCH_CACHE_TTL_HOURS", "12"))
DETAIL_CACHE_TTL_HOURS = float(os.environ.get("DETAIL_CACHE_TTL_HOURS", "72"))
# Opening a product page fetches its 1688 detail when stale (one detail call).
# Set to "false" to stop spending detail credits on page views.
DETAIL_AUTO_FETCH = os.environ.get("DETAIL_AUTO_FETCH", "true").lower() == "true"

# 1688 prices are CNY. Converted once at ingest; override with a live rate.
CNY_TO_USD = float(os.environ.get("CNY_TO_USD", "0.14"))

# 1688 gives wholesale cost only. The suggested resale price shown to users is
# cost x this markup (3x is the usual dropshipping rule of thumb).
RETAIL_MARKUP = float(os.environ.get("RETAIL_MARKUP", "3.0"))

# Seed keywords the ingestion worker (`python -m app.worker`) pulls on a
# schedule to fill /products/trending. 1688 search expects Chinese keywords;
# the key is the category the frontend filters on.
TRENDING_KEYWORDS: dict[str, list[str]] = {
    "fashion": ["衣服", "女装"],
    "beauty": ["美妆工具"],
    "electronics": ["手机配件"],
    "home": ["家居用品"],
    "pets": ["宠物用品"],
    "fitness": ["健身器材"],
}

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
