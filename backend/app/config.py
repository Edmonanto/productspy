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
