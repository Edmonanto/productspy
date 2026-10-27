# ProductSpy Pro — API

FastAPI backend for productspy.pro (the Next.js frontend in the repo root).
Mounted at `/api/v1` to match the frontend's `NEXT_PUBLIC_API_URL`.

ProductSpy Pro does one thing: **Daily Winners** — every day, per market, the
5-10 products advertisers are scaling right now, read from the Facebook Ad
Library, TikTok Creative Center and TikTok, with the evidence behind each pick.

```
app/
  routers/winners.py    picks, evidence, markets, CSV
  routers/users.py      /users/me (starts the free trial)
  routers/watchlist.py  saved products
  routers/billing.py    Stripe + PayPal, /billing/trial
  winners/              the engine: collectors, extraction, scoring, worker
  trial.py              7-day trial rules + daily housekeeping job
  repository.py         account-side SQL (watchlist, subscriptions, webhooks)
```

## Auth

There is no second user system. Supabase remains the identity provider; this
API verifies the access token the browser already holds and reads `sub` as the
user id. Tokens signed ES256/RS256 are checked against the project's JWKS
(`SUPABASE_URL`); legacy HS256 tokens against `SUPABASE_JWT_SECRET`. Rows are
keyed by that uuid.

## Running locally

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-winners.txt
playwright install chromium
cp .env.example .env
python -m app.migrate
uvicorn app.main:app --reload --port 8000
```

Fill `DATABASE_URL` and `SUPABASE_URL` in `.env` before running migrate.
`requirements-winners.txt` is the API's `requirements.txt` plus Playwright,
which only the daily scan needs.

> Commands in this README carry no trailing `#` comments on purpose. zsh — the
> default macOS shell — does **not** treat `#` as a comment interactively, so a
> pasted `cp .env.example .env  # fill this in` runs `cp` with every following
> word as an argument and fails with `cp: <word>: Not a directory`.

Then fill the dashboard with a real scan:

```bash
python -m app.winners.worker --market US
```

Interactive docs at http://localhost:8000/docs, health at `/health`. Point the
frontend at it with `NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1`.

## Tests

```bash
pip install -r requirements-dev.txt
pytest tests/ -q
```

The database layer is stubbed, so no Postgres is required.

`tests/test_sql_integrity.py` covers the gap that stubbing leaves: because no
query executes during the suite, the first real run of this SQL would
otherwise be in production. It statically checks every query in
`repository.py` and `winners/store.py`: columns exist in the migrations, `$N`
placeholders match the arguments, nothing touches a dropped table, and — via
`pglast`, bindings to PostgreSQL's own parser — every migration and query is
valid Postgres.

## Endpoints

| Endpoint | |
| --- | --- |
| `GET /users/me` | profile, effective plan, trial (starts the trial on first visit) |
| `GET /winners?market=&date=` | the day's picks; beyond the plan's allowance only rank + score |
| `GET /winners/dates` | archive days within the plan's history |
| `GET /winners/products/{id}` | score history, ads/videos (paid plans), suppliers |
| `GET /winners/markets` · `POST /winners/preferences` | markets followed (plan caps the count) |
| `GET /winners/export.csv` | Pro / Agency |
| `GET /winners/status` | last scan per market |
| `GET /watchlist/` · `POST` · `DELETE` | saved products; free plan capped at 10 |
| `GET /billing/status` · `POST /billing/checkout` `portal` `cancel` `trial` | Stripe + PayPal |
| `POST /billing/webhook/{stripe,paypal}` | signature-verified, idempotent |
| `python -m app.winners.worker` | the daily scan |
| `python -m app.trial` | trial reminder emails + expiry |

## Migrations

```bash
python -m app.migrate
```

Applies every file in `migrations/` in filename order and records each in a
`schema_migrations` ledger. All the SQL is idempotent, so re-running is
harmless — the ledger exists so a deploy reports *which* migrations it
applied instead of silently re-executing everything.

A migration whose content changed after being applied is re-applied with a
warning rather than skipped: a checksum drift means the database and this
checkout disagree, and that should be visible.

The API applies pending migrations on startup (`MIGRATE_ON_START=true`, the
default): a failure aborts startup and Render keeps the previous version live.
The Daily Winners cron also runs `python -m app.migrate` first and chains it
with `&&`, so a broken migration stops the run.

`014_winners_only.sql` permanently deletes the old marketplace catalogue
(every product not from Daily Winners) and the tables only it used. Take a
Supabase backup first if you might want it back.

## Daily Winners

The engine reads **advertising** — the Facebook Ad Library, TikTok Creative
Center's Top Ads, and TikTok product-discovery hashtags — once a day per
market, groups the ads into products, scores them, and picks the 5-10
strongest.

```bash
python -m app.winners.worker --collectors   # which sources are active
python -m app.winners.worker --market US    # one market
python -m app.winners.worker                # every market in WINNERS_MARKETS
```

```
collect -> ad_creatives -> Claude names + dedupes the product -> price & cost
        -> aggregate signals -> score 0-100 -> daily_winners (5-10 per market)
```

**Markets**: US, UK, EU, FR, DE, CA, AU, AE (UAE/Dubai), SA — `app/winners/markets.py`.
Users choose theirs in Settings; the plan caps how many (`WINNERS_PLANS` in config).

**Sources** (`app/winners/collectors/`), free by default:

| Source | How | Notes |
| --- | --- | --- |
| Facebook Ad Library, EU/FR/DE | Official Graph API (`META_ACCESS_TOKEN`) | The API only returns *commercial* ads that ran in the EU (DSA), with reach. Needs a Meta app + ID verification. |
| Facebook Ad Library, other markets | Playwright, reads the JSON the page loads | No login. Use a residential proxy for volume. |
| TikTok Creative Center Top Ads | Playwright | CTR, likes, budget level, landing page. |
| TikTok videos | Playwright on #tiktokmademebuyit, #amazonfinds… | Samples comments for buying intent. Results follow the visitor's country — set `PROXY_URL_<MARKET>`. |
| Apify (paid) | `USE_APIFY=true` + `APIFY_TOKEN` | Replaces the scrapers; actor ids configurable. |

The scrapers parse the JSON the pages download, not their HTML, which survives
most redesigns — but both platforms change, so expect to adjust a collector
occasionally. Scraping is against both platforms' terms; the official Meta API
and Apify are the lower-risk routes.

**Product extraction** (`extract.py`): Claude names the one physical product
each ad sells in generic words, gives a canonical key ("posture-corrector"),
and flags brand/IP copies, restricted items, fragile/heavy and seasonal goods,
plus a rough supplier cost. Near-duplicate keys merge. Without
`ANTHROPIC_API_KEY` a Shopify-URL/title heuristic stands in. Products land in
`products` with `source = 'winners'`.

**Price & cost** (`enrich.py`): Shopify's free `/products/<slug>.json`, else
JSON-LD / `og:price`; FX via `config.usd_rates()` (unlisted currency → no
price, never a guess). Supplier cost from an AliExpress search when it answers,
else Claude's estimate — flagged `cost_estimated` and counted 20% lower.

### The score (`app/winners/scoring.py`)

| Pillar | Pts | Signals |
| --- | --- | --- |
| Scaling proof | 30 | longest-running ad (14d+/30d+), # creatives, new creatives in 7 days, EU reach or TikTok budget level |
| Engagement | 25 | TikTok engagement rate, share ratio, % buying-intent comments, ad CTR |
| Proven demand | 20 | 3-15 different stores (the sweet spot), # creators, total views |
| Margin | 15 | sell ≥ 3× cost, $20-60 price |
| Freshness | 10 | first seen recently, views/hour on recent videos, wow / problem-solving |

Penalties: >30 stores −5, >50 −10, fragile/heavy −5, seasonal −3, brand
look-alike −3, one platform only −5, ads <4 days old with no organic proof −5.
Hard filters: restricted, high IP risk, not a physical product, picked in the
last 30 days.

Missing data is never zero — each pillar scores what is known, scaled up, but
capped at 60% below 40% coverage, so a product needs real evidence to rank.
Up to 10 products ≥ 70 are picked; if fewer than 5 qualify, the best 60-69
fill to 5, labelled **rising**.

### Deploy

`productspy-winners` in `render.yaml`: a Docker cron (`Dockerfile.winners`,
on the official Playwright image — the native Python runtime lacks Chromium's
system libraries) at 01:00 UTC, on the `standard` plan because Chromium needs
memory. It runs migrations, trial housekeeping, then the scan. Each market is
logged in `winner_runs`; the worker exits non-zero if no market produced picks.

## Free trial

Every new account gets **7 days of Pro, no card** (`TRIAL_DAYS`, `TRIAL_PLAN`).

- `GET /users/me` — called on every dashboard load — writes the first
  subscription row as `status='trialing'`, `provider='none'`. That pairing is
  what marks an app trial: webhooks always write their provider, and Stripe's
  own `trialing` is mapped to `active`.
- Access is decided at read time (`app/trial.py: effective_plan`):
  `repository.subscription()` returns Free for an expired trial before any job
  runs, so every quota and plan check is trial-aware without changes.
- Accounts that predate the trial get `POST /billing/trial` (once —
  `trial_used`, enforced in the UPDATE's WHERE clause).
- Paying by card during the trial passes `trial_end` to Stripe Checkout, so
  the first charge lands when the trial ends (skipped when < 48h remain —
  Stripe refuses those).
- `python -m app.trial` (inside the winners cron) emails at ~2 days and on
  the last day, then downgrades expired trials and emails them. Email goes
  through Resend (`RESEND_API_KEY`, `EMAIL_FROM`); without a key the trial
  still works, silently.

The API applies pending migrations on startup (`MIGRATE_ON_START`), so a
deploy brings `012_winners.sql` / `013_free_trial.sql` in by itself.

## Billing

Stripe and PayPal, selected per checkout by the `provider` query param the
frontend already sends. Plans live in `app/config.py` (`WINNERS_PLANS`); the price /
plan ids come from env (`STRIPE_PRICE_*`, `PAYPAL_PLAN_*`).

**Subscription state is only ever written from a verified webhook.** The
browser's return from a checkout URL is never treated as proof of payment —
anyone can navigate to the success URL, so trusting it would hand out free
upgrades. `POST /billing/webhook/stripe` verifies the Stripe signature;
`POST /billing/webhook/paypal` calls PayPal's verify-webhook-signature
endpoint. Neither accepts an unverified payload.

Deliveries are idempotent: `billing_events` has a unique key on
`(provider, event_id)`, so a retried or replayed event is a no-op rather than
a second upgrade. Processing failures are recorded and return 500 so the
provider retries.

Cancelling sets `cancel_at_period_end` — the user keeps what they paid for
until the period closes. PayPal has no hosted billing portal, so `/portal`
returns PayPal's own automatic-payments page for PayPal subscribers rather
than pretending we host one.

Register the webhook endpoints in each dashboard and put the signing secrets
in `STRIPE_WEBHOOK_SECRET` / `PAYPAL_WEBHOOK_ID`. Use
`PAYPAL_API_BASE=https://api-m.sandbox.paypal.com` while testing.


## Remaining work

The collectors are untested against the live sites from CI (they can't be
reached from the build sandbox): run `python -m app.winners.worker --market US`
once with real network access and check `winner_runs` before relying on the
schedule. Billing is untested against live provider accounts — run Stripe's
`stripe listen --forward-to localhost:8000/api/v1/billing/webhook/stripe` and a
PayPal sandbox subscription before switching real keys on.

## Research engine (scoring v2, AI reports, validation)

**Score** (`app/winners/scoring.py`): eight criteria, default weights demand 20 · profitability 20 ·
competition 15 · creative 10 · differentiation 10 · logistics 10 · market fit 10 · risk 5
(override with `WINNERS_WEIGHTS='{"demand": 25}'`, always rescaled to 100). Each criterion stores
its evidence tagged observed / calculated / ai / assumption. Criteria without data are left out
(never zero); single-platform products cap at 85; a "winner" (70+) needs medium/high confidence.
Bands: 85+ exceptional · 70–84 strong · 55–69 promising · 40–54 weak · <40 low.

**Unit economics** (`app/winners/economics.py`, mirrored in `src/lib/profit.ts`): contribution
before/after ads, break-even CPA and ROAS, scenarios, sensitivity. Deterministic; missing inputs
→ incomplete. Tests: `tests/test_economics.py`.

**AI research report** (`app/winners/research.py`, `POST /research/{id}/report`): evidence pack
(ads, safely fetched competitor pages — `safe_fetch.py` blocks private/internal addresses —,
suppliers, calculated score/economics) → OpenAI JSON mode → pydantic validation (one retry) →
source-id check, unverified-number check, price-range sanity check → cached
`RESEARCH_CACHE_DAYS` (7). Plan limit `reports_per_day` in `WINNERS_PLANS`.

**Validation workflow**: `GET/PUT /research/{id}/validation[/{stage}]`, `PUT /research/{id}/results`.
**Compare**: `GET /research/compare?ids=…` (plan `compare_max`). **Usage**: `GET /research/usage` (admins).

| Env | Default | |
|---|---|---|
| `OPENAI_RESEARCH_MODEL` | `OPENAI_MODEL` | model for reports |
| `LLM_DAILY_CALL_CAP` | 3000 | AI calls/day, 0 = no cap |
| `APIFY_DAILY_RUN_CAP` | 60 | Apify runs/day, 0 = no cap |
| `RESEARCH_CONCURRENCY` | 3 | reports generated at once |
| `RESEARCH_CACHE_DAYS` | 7 | reuse a report this long |
| `WINNERS_WEIGHTS` | — | JSON weight overrides |

Migration `017_research.sql` adds `product_reports`, `report_requests`, `validation_steps`,
`validation_results` and token/item columns on `api_usage`.
