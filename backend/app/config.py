"""Runtime configuration, read from the environment.

Locally, backend/.env is loaded first so `python -m app.winners.worker` and
`python -m app.migrate` work straight from a terminal. Real environment
variables always win (override=False), so on Render — where the env group is
injected — the file is irrelevant even if one were present.
"""
import os
import pathlib

from dotenv import load_dotenv

load_dotenv(pathlib.Path(__file__).resolve().parent.parent / ".env", override=False)

# ── Core ────────────────────────────────────────────────────────────────────
DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Supabase JWT verification. Supabase signs access tokens with this shared
# secret (Project Settings -> API -> JWT Secret) using HS256.
# Supabase signs access tokens one of two ways:
#
#   - asymmetric (ES256/RS256), the current default. The token header carries
#     a `kid`; the matching public key is published at the project's JWKS
#     endpoint. Nothing secret is needed to verify one.
#   - legacy HS256, using the shared secret below (Project Settings -> API ->
#     JWT Secret). Still valid for projects that have not rotated.
#
# Both are accepted. The algorithm in the token header decides which path
# runs, and an unexpected algorithm is refused rather than guessed at.
SUPABASE_JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_JWKS_URL = os.environ.get("SUPABASE_JWKS_URL", "") or (
    f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json" if SUPABASE_URL else ""
)
JWT_ALGORITHM = "HS256"
ASYMMETRIC_ALGORITHMS = ("ES256", "RS256")
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

# Apply pending migrations when the API starts (see main.lifespan).
MIGRATE_ON_START = os.environ.get("MIGRATE_ON_START", "true").lower() == "true"

# Comma-separated emails of admins: they answer quote requests at
# /dashboard/quotes (and get an "Admin" badge).
ADMIN_EMAILS = {
    e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()
}
# Who gets "something failed" emails (app/alerts.py). Empty = ADMIN_EMAILS.
ALERT_EMAILS = {
    e.strip().lower() for e in os.environ.get("ALERT_EMAILS", "").split(",") if e.strip()
}

# ── Plans ───────────────────────────────────────────────────────────────────
# Mirrors the PLANS array in src/app/dashboard/billing/page.tsx.
# Daily Winners limits are WINNERS_PLANS, further down.
UNLIMITED = "unlimited"

PLAN_WATCHLIST_LIMITS: dict[str, int | str] = {
    "free": 10,
    "starter": UNLIMITED,
    "pro": UNLIMITED,
    "agency": UNLIMITED,
}

DEFAULT_PLAN = "free"

# ── Currency ────────────────────────────────────────────────────────────────
# FX to USD for store prices. An unconverted price is worse than none — a
# margin would read 229 EUR as 229 USD — so an unlisted currency drops the price.
USD_PER_GBP = float(os.environ.get("USD_PER_GBP", "1.27"))
USD_PER_EUR = float(os.environ.get("USD_PER_EUR", "1.08"))
USD_PER_CAD = float(os.environ.get("USD_PER_CAD", "0.73"))
USD_PER_AUD = float(os.environ.get("USD_PER_AUD", "0.66"))
USD_PER_AED = float(os.environ.get("USD_PER_AED", "0.272"))
USD_PER_SAR = float(os.environ.get("USD_PER_SAR", "0.267"))


def usd_rates() -> dict[str, float]:
    """Multiplier from each currency to USD. Unlisted -> price dropped."""
    return {
        "USD": 1.0,
        "GBP": USD_PER_GBP,
        "EUR": USD_PER_EUR,
        "CAD": USD_PER_CAD,
        "AUD": USD_PER_AUD,
        "AED": USD_PER_AED,
        "SAR": USD_PER_SAR,
    }


# ── Claude ──────────────────────────────────────────────────────────────────
# Names the product behind each ad, dedupes, and flags IP/restricted risk.
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

# Monthly list prices (USD) — must match the billing page and the Stripe/PayPal
# prices created by `python -m app.billing.setup`.
PLAN_PRICES_USD: dict[str, float] = {"starter": 19.99, "pro": 69.99, "agency": 199}

# PayPal can't apply coupons: referred customers subscribe to these plans,
# whose first month is billed at the partner discount (setup.py creates them).
PAYPAL_PARTNER_PLAN_IDS: dict[str, str] = {
    "starter": os.environ.get("PAYPAL_PARTNER_PLAN_STARTER", ""),
    "pro": os.environ.get("PAYPAL_PARTNER_PLAN_PRO", ""),
    "agency": os.environ.get("PAYPAL_PARTNER_PLAN_AGENCY", ""),
}

PAYPAL_PLAN_IDS: dict[str, str] = {
    "starter": os.environ.get("PAYPAL_PLAN_STARTER", ""),
    "pro": os.environ.get("PAYPAL_PLAN_PRO", ""),
    "agency": os.environ.get("PAYPAL_PLAN_AGENCY", ""),
}

PAID_PLANS = ("starter", "pro", "agency")


# ── Daily Winners engine ────────────────────────────────────────────────────
# Scans the Facebook Ad Library, TikTok Creative Center (Top Ads) and TikTok
# hashtags once a day per market, and picks the 5-10 strongest products.
# See backend/README.md#daily-winners.

# Markets the daily worker scans (codes from app/winners/markets.py).
# Markets that are scanned daily AND offered to users (launch: US, UK, France).
WINNERS_MARKETS = os.environ.get("WINNERS_MARKETS", "US,UK,FR")

# Claude names each ad's product, dedupes, and flags IP/restricted risk.
# Without a key a URL/title heuristic stands in (fewer products recognised).
WINNERS_MODEL = os.environ.get("WINNERS_MODEL", "") or ANTHROPIC_MODEL
# Alternative to Claude for product naming: any OpenAI-compatible API.
# Used only when no Anthropic key is set. OPENAI_BASE_URL also lets you point
# at a compatible provider/reseller.
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
# Model for the per-product AI research report (defaults to OPENAI_MODEL).
OPENAI_RESEARCH_MODEL = os.environ.get("OPENAI_RESEARCH_MODEL", "") or OPENAI_MODEL

# Cost controls for paid APIs (app/usage.py). A cap of 0 means no cap.
LLM_DAILY_CALL_CAP = int(os.environ.get("LLM_DAILY_CALL_CAP", "3000"))
APIFY_DAILY_RUN_CAP = int(os.environ.get("APIFY_DAILY_RUN_CAP", "60"))
RESEARCH_CONCURRENCY = int(os.environ.get("RESEARCH_CONCURRENCY", "3"))
RESEARCH_CACHE_DAYS = int(os.environ.get("RESEARCH_CACHE_DAYS", "7"))

# Sources. All free by default; Apify replaces the scrapers when enabled.
COLLECT_META = os.environ.get("COLLECT_META", "true").lower() == "true"
COLLECT_TIKTOK_ADS = os.environ.get("COLLECT_TIKTOK_ADS", "true").lower() == "true"
COLLECT_TIKTOK_ORGANIC = os.environ.get("COLLECT_TIKTOK_ORGANIC", "true").lower() == "true"

# Meta Ad Library API. Only returns *commercial* ads delivered in the EU
# (Digital Services Act), so it serves the EU/FR/DE markets; the rest use the
# Playwright web scraper. Needs a Meta developer app with ID verification.
META_ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN", "")
META_GRAPH_VERSION = os.environ.get("META_GRAPH_VERSION", "v23.0")
META_WEB_SCRAPER = os.environ.get("META_WEB_SCRAPER", "true").lower() == "true"

# Residential proxy for the scrapers. TikTok results depend on the visitor's
# country, so PROXY_URL_<MARKET> (e.g. PROXY_URL_AE) overrides this per market.
PROXY_URL = os.environ.get("PROXY_URL", "")

# Paid, lower-maintenance sources (apify.com).
USE_APIFY = os.environ.get("USE_APIFY", "").lower() == "true"
APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "")
APIFY_META_ACTOR = os.environ.get("APIFY_META_ACTOR", "curious_coder~facebook-ads-library-scraper")
APIFY_TIKTOK_ACTOR = os.environ.get("APIFY_TIKTOK_ACTOR", "clockworks~tiktok-scraper")
APIFY_TIKTOK_ADS_ACTOR = os.environ.get("APIFY_TIKTOK_ADS_ACTOR", "")
# Apify spend control: items fetched per market per scan, and how often a
# market may be scraped (a re-run the same day reuses what's already stored).
APIFY_META_MAX = int(os.environ.get("APIFY_META_MAX", "150"))
APIFY_TIKTOK_MAX = int(os.environ.get("APIFY_TIKTOK_MAX", "40"))
APIFY_TRENDS_MAX = int(os.environ.get("APIFY_TRENDS_MAX", "10"))  # Google Trends lookups per market per day (7-day cache)
APIFY_MIN_HOURS_BETWEEN = int(os.environ.get("APIFY_MIN_HOURS_BETWEEN", "20"))
# Google Trends search interest (app/winners/trends.py). Empty = off.
# Default: an API-based actor (no browser) — ~$0.005 per term and seconds per
# term. apify~google-trends-scraper loads Google's page in a browser and, since
# Google removed the related-queries widgets, retries every term until it times
# out (~$0.30 per term); it is only the fallback now.
APIFY_TRENDS_ACTOR = os.environ.get("APIFY_TRENDS_ACTOR", "signalbench~google-trends-scraper")
APIFY_TRENDS_FALLBACK = os.environ.get("APIFY_TRENDS_FALLBACK", "apify~google-trends-scraper")

TIKTOK_MIN_VIEWS = int(os.environ.get("TIKTOK_MIN_VIEWS", "100000"))
TIKTOK_CC_PERIOD = os.environ.get("TIKTOK_CC_PERIOD", "7")  # 7 | 30 | 180 days
ENRICH_ALIEXPRESS = os.environ.get("ENRICH_ALIEXPRESS", "true").lower() == "true"


def winners_markets() -> list[str]:
    return [m.strip().upper() for m in WINNERS_MARKETS.split(",") if m.strip()]


# What each plan unlocks in Daily Winners. Mirrors PLANS in
# src/app/dashboard/billing/page.tsx.
WINNERS_PLANS: dict[str, dict[str, int | bool]] = {
    #            markets  picks/day  history  ad evidence  csv  AI reports/day  compare
    "free":    {"markets": 1,  "winners_per_day": 3,  "history_days": 0,  "ad_evidence": False, "export_csv": False,
                "reports_per_day": 1, "compare_max": 2},
    "starter": {"markets": 1,  "winners_per_day": 10, "history_days": 7,  "ad_evidence": True,  "export_csv": False,
                "reports_per_day": 5, "compare_max": 3},
    "pro":     {"markets": 3,  "winners_per_day": 10, "history_days": 30, "ad_evidence": True,  "export_csv": True,
                "reports_per_day": 20, "compare_max": 5},
    "agency":  {"markets": 99, "winners_per_day": 10, "history_days": 90, "ad_evidence": True,  "export_csv": True,
                "reports_per_day": 100, "compare_max": 5},
}


# ── Free trial ──────────────────────────────────────────────────────────────
# Every new account starts on TRIAL_PLAN for TRIAL_DAYS, no card. When it ends
# the account is Free unless the user subscribed. See app/trial.py.
TRIAL_DAYS = int(os.environ.get("TRIAL_DAYS", "7"))
TRIAL_PLAN = os.environ.get("TRIAL_PLAN", "pro")

# Transactional email (trial reminders) via Resend. Optional: without a key
# the trial still works, it just isn't announced by email.
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
EMAIL_FROM = os.environ.get("EMAIL_FROM", "ProductSpy Pro <hello@productspy.pro>")
# Daily winners email (app/winners/digest.py). Links in emails point at the
# public API for one-click unsubscribe; DIGEST_SECRET signs those links
# (falls back to the Supabase JWT secret).
API_PUBLIC_URL = os.environ.get("API_PUBLIC_URL", "https://productspy-api.onrender.com/api/v1").rstrip("/")
DIGEST_SECRET = os.environ.get("DIGEST_SECRET", "")
