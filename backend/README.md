# ProductSpy Pro — API

FastAPI backend for the Next.js frontend in the repo root. Mounted at
`/api/v1` to match the frontend's `NEXT_PUBLIC_API_URL`.

## Why FastAPI

The frontend's `src/lib/api.ts` already assumes this shape: a versioned
`/api/v1` prefix, `snake_case` fields, `{"detail": "..."}` error bodies and a
`Authorization: Bearer <supabase jwt>` header. Those are FastAPI defaults, and
Python is the right tool for the Phase 2 scraping and scoring work.

## Auth

There is no second user system. Supabase remains the identity provider; this
API verifies the access token the browser already holds (HS256, signed with the
project's JWT secret) and reads `sub` as the user id. Rows are keyed by that
uuid.

## Running locally

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # fill in DATABASE_URL + SUPABASE_JWT_SECRET
psql "$DATABASE_URL" -f migrations/001_init.sql
uvicorn app.main:app --reload --port 8000
```

Interactive docs at http://localhost:8000/docs, health at `/health`.

Point the frontend at it with `NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1`.
As soon as `products` has rows, the dashboard stops falling back to
`src/lib/demo-products.ts` and renders real data.

## Tests

```bash
pytest tests/ -q
```

The database layer is stubbed, so no Postgres is required.

## Endpoint status

| Endpoint | Status |
| --- | --- |
| `GET /users/me` | done — profile, subscription, live quota |
| `GET /products/trending` | done — filters by source, category, min_score |
| `GET /products/search` | done — charges daily search quota (429 when spent) |
| `GET /products/{id}` | done |
| `POST /products/{id}/rescore` | done — recomputes all four components from snapshot history |
| `GET /watchlist/` `POST` `DELETE` | done — free plan capped at 10 |
| `GET /billing/status` | done — reads real subscription rows |
| `POST /billing/checkout` `portal` `cancel` | done — Stripe + PayPal |
| `POST /billing/webhook/{stripe,paypal}` | done — signature-verified, idempotent |
| `python -m app.ingest.worker` | done — scheduled ingestion + scoring + summaries |

## Ingestion (the engine)

```bash
python -m app.ingest.worker
```

Per provider: fetch → upsert → **snapshot** → score → summarise. On Render it
runs as a cron job every 6 hours (see `render.yaml`); each run also writes a
`product_snapshots` row per product.

Providers are opt-in by credential — set the keys and the source turns on:

| Provider | Env | Gives you |
| --- | --- | --- |
| **1688 Open Platform** | `ALIBABA1688_APP_KEY` / `_SECRET` | Real **wholesale/factory cost** in CNY, plus MOQ and sales volume. The best cost signal available — margin scoring is only as good as this number. |
| AliExpress Affiliate | `ALIEXPRESS_APP_KEY` / `_SECRET` | Retail price + orders. Official, free after Portals approval; affiliate catalogue only. |
| **Apify — AliExpress** | `APIFY_TOKEN` alone | **No approval needed.** Full AliExpress catalogue (not just the affiliate subset). Actor defaults to `thirdwatch/aliexpress-product-scraper`, billed pay-per-event. |
| Apify — other actors | `APIFY_TOKEN` + `APIFY_*_ACTOR` | Amazon / TikTok / Facebook Ad Library. One actor per source. |

**Fastest route to real data:** set `APIFY_TOKEN` and run the worker. No
affiliate approval, no real-name verification, and products land under
`source="aliexpress"` so they share a catalogue with the official provider if
you switch later.

`APIFY_QUERIES` is the important one — the actor searches those terms, so that
list *is* your catalogue. It returns nothing without them.

Actor input schemas are not standardised between authors. The default shape
(`{queries, maxResults, category, country}`) was verified against this actor's
own example run input; if you switch actors, set `APIFY_INPUT_JSON` to the raw
JSON that actor expects. A wrong shape returns an **empty dataset with HTTP
200**, so the worker logs a loud warning on zero items rather than treating it
as "no results today".

Pricing is pay-per-event and set by the actor author — check the actor's page
for the current rate before scheduling frequent runs.

### 1688 notes

1688 is Alibaba's **domestic Chinese wholesale** marketplace, so its auth
differs from AliExpress in three ways — do not copy that client:

* gateway `gw.open.1688.com` with a `param2/{version}/{namespace}/{api}/{appKey}` path,
* signature is **HMAC-SHA1**, uppercase hex (AliExpress uses SHA256),
* the signed string begins with the URL path, then the sorted params.

`ALIBABA1688_NAMESPACE` and `ALIBABA1688_API_NAME` are configurable because
which call you may invoke depends on the service package granted to your app.
Set them to match your grant rather than trusting the defaults.

**Wholesale listings have no retail price.** `cost_usd` is the real number
(converted at `CNY_PER_USD`); `price_usd` is *derived* as
`cost × WHOLESALE_MARKUP` (default 3.0) purely so margin scoring has an
anchor. It is an assumption, not an observed market price — replace it with a
real retail comparison (Amazon/AliExpress for the same product) before
presenting margin as fact to paying users.

**Access reality:** the 1688 Open Platform is Chinese-language and normally
requires real-name verification (Chinese mobile + Alipay), and some API
packages require a business entity. It is not necessarily an easier gate than
AliExpress — verify you can register before betting the roadmap on it.

With no credentials set the worker logs what's missing and exits 1 without
touching the database.

**The AliExpress request signature is implemented from their published scheme
but has not been exercised against a live approved account** — verify the first
run's response before trusting the schedule.

## Scoring

`app/scoring.py`. Weights: demand 30%, margin 30%, trend 25%, competition 15%.

- **margin** — gross margin from `price_usd` vs `cost_usd`; 70%+ saturates at 100.
- **demand** — units sold, log-scaled so the top end doesn't dominate.
- **competition** — inverted ad volume; few advertisers scores high.
- **trend** — **order velocity between two of our own snapshots.** This is the
  part no provider sells you: after ~2 weeks of runs, "orders grew 40%
  week-over-week" is computed from `product_snapshots`, not bought.

Any signal we lack returns a neutral **50**, never a flattering 100 — an
unknown must not outrank a product with proven numbers. `trend` therefore stays
neutral until history reaches `TREND_WINDOW_DAYS` back.

`ai_summary` is one Claude call per product during ingestion (`app/summarize.py`),
written only when a product has none, so re-runs cost nothing. Set
`ANTHROPIC_API_KEY` to enable it; without it, ingestion runs and summaries stay
empty. Model via `ANTHROPIC_MODEL` (default `claude-opus-5`).

## Billing

Stripe and PayPal, selected per checkout by the `provider` query param the
frontend already sends. Plans and quotas live in `app/config.py`; the price /
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

Run `migrations/003_billing.sql` before deploying this.

## Remaining work

Nothing blocking. Untested against live provider accounts — run Stripe's
`stripe listen --forward-to localhost:8000/api/v1/billing/webhook/stripe` and
a PayPal sandbox subscription before switching real keys on.
