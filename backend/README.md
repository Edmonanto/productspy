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
pip install -r requirements-dev.txt   # adds pglast for the SQL grammar checks
```

The database layer is stubbed, so no Postgres is required.

`tests/test_sql_integrity.py` covers the gap that stubbing leaves: because no
query executes during the suite, the first real run of this SQL would
otherwise be the first production ingestion. It statically checks that every
query references columns the migrations actually create, that `$N`
placeholders match the arguments passed, and — via `pglast`, bindings to
PostgreSQL's own parser — that every migration and query is valid Postgres.
The grammar checks skip cleanly when `pglast` isn't installed.

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

### Amazon (`AMAZON_*`)

The **retail price anchor**. 1688 gives a real wholesale cost but no retail
price; Amazon gives an observed retail price for the same class of product.

* `AMAZON_SITES` is a list of marketplaces (`US,UK,DE`) crossed with
  `AMAZON_KEYWORDS`, so three sites x three keywords is nine calls.
* **ASINs are namespaced by site** (`US:B09G9FPHY6`). The same ASIN exists on
  several marketplaces at different prices, so without the site in the
  identity the US and DE rows collide on `(source, external_id)`.
* **No sales count.** Amazon does not publish one, so `orders_count` stays
  `None`. Review count is a popularity proxy, not units sold — substituting
  it would fabricate demand.
* Non-USD prices are converted via `USD_PER_GBP` / `USD_PER_EUR`. A currency
  with no configured rate has its price **dropped**, because an unconverted
  price is worse than none: margin would read 229 EUR as 229 USD.

**Locale is the trap.** The API returns display strings, not numbers, and the
German format inverts the separators:

| | price | rating | reviews |
| --- | --- | --- | --- |
| US | `$501.60` | `4.5 out of 5 stars` | `(75,618)` / `(11.9K)` |
| UK | `£8.99` | `4.6 out of 5 stars` | `(45.4K)` |
| DE | `229,99€` | `4,6 von 5 Sternen` | `(36.976)` |

In DE a dot groups thousands, so a naive `float()` reads `36.976` as 36.976
reviews instead of 36,976 — a 1000x error — and reads `10,99 €` as 1099 or
nothing. Parsing is site-aware and the tests pin both readings of the same
string.

> **Scoring caveat.** With no cost and no sales count, every Amazon product
> scores the neutral 50 on demand, margin and competition, so they all rank
> identically. Amazon earns its place as a price *reference* for
> cross-platform matching — which does not exist yet. Until it does, expect
> Amazon rows to sit in an undifferentiated block.

### TikTok Shop (`TIKTOK_*`)

The strongest source for this product: `sold_count` and its change over time
feed **demand and trend — 55% of the overall score** — and it is the only
source here reporting a **real USD retail price** rather than a derived one.

* `TIKTOK_KEYWORDS` is the catalogue; one search call returns up to ~30
  products for ¥0.05. Result counts vary a lot by keyword (30 for `cat`, 4
  for `cat bed`), so use several.
* `TIKTOK_SELLER_IDS` pulls a specific shop's catalogue — same payload shape.
* Detail enrichment is capped (`TIKTOK_ENRICH_TOP`, default 0): one call per
  product, and it overlays the true sold_count and the live sale price.
* **No supplier cost.** TikTok never exposes it, so `cost_usd` stays `None`
  and margin scores neutral rather than zero (see Scoring).
* Prices are only trusted when quoted in USD; a localised storefront is
  dropped rather than misread as dollars.
* `charged_yuan`/`balance_yuan` are logged on every call so spend is visible.

> The `product/reviews` endpoint is **not used** — it returns
> `{"code":"error","msg":"调用失败"}` for every parameter combination tried,
> and reviews are already embedded in the detail response under `review_info`.
> The aggregator is also intermittently flaky on otherwise-valid requests, so
> each call is retried once.

### 1688 via aggregator (no approval)

`AGG1688_*` points at a third-party reseller that proxies 1688's internal
mtop API, so it needs only a token — no Open Platform account. Verified
end-to-end against the live endpoints: one keyword search returns ~60 offers
for one unit of quota.

* **`AGG1688_KEYWORDS` is the catalogue.** One search call per keyword.
* **Detail enrichment is opt-in and capped** (`AGG1688_ENRICH_TOP`, default 0)
  because detail costs one call *per product* and would drain quota in a run.
  It overlays the real tiered/MOQ price, which is better than the search price.
* **P4P results are dropped by default.** They are paid placement, so counting
  them as demand would let advertisers buy their way up our rankings. In the
  live check this took 60 raw results down to 50 organic ones.
* Titles arrive with the matched keyword wrapped in `<font>` tags, and sold
  counts are Chinese strings (`已售1.3万+件` = 13,000 — naive parsing reads
  that as 1). Both are handled; `tests/fixtures/` holds trimmed copies of real
  responses so an upstream schema change fails a test instead of silently
  ingesting nothing.
* The provider logs `left_nums` after each search — watch it for quota burn.

> ⚠️ These endpoints are **plain HTTP on bare IPs**. The token and the
> response travel unencrypted, and the operator is unknown. Keep tokens in
> env, rotate them if they leak, and treat this as a bootstrap source rather
> than something to build a paid product on permanently.

### 1688 notes (official Open Platform)

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

Any signal we lack returns a neutral **50** — never a flattering 100, and
equally never a punishing 0. An unknown must not outrank a product with
proven numbers, nor be buried beneath one. This matters because sources
disagree on what they publish: TikTok gives retail with no supplier cost,
1688 the reverse. Scoring a missing cost as *zero margin* would rank every
TikTok product below every 1688 one for a reason that has nothing to do with
the product. A genuine zero — price at or below cost — still scores 0. `trend` therefore stays
neutral until history reaches `TREND_WINDOW_DAYS` back.

`ai_summary` is one Claude call per product during ingestion (`app/summarize.py`),
written only when a product has none, so re-runs cost nothing. Set
`ANTHROPIC_API_KEY` to enable it; without it, ingestion runs and summaries stay
empty. Model via `ANTHROPIC_MODEL` (default `claude-opus-5`).

## Matching (cross-platform, v1)

```bash
python -m app.matching.runner
```

Links a retail listing (TikTok/Amazon: real price, no cost) to a supplier
listing (1688: real cost, no retail), so margin can come from two observed
numbers instead of the `cost x WHOLESALE_MARKUP` guess.

**A wrong match is worse than no match** — it would report a confident margin
on a pairing that doesn't exist, and a subscriber could order against it.
Everything below follows from that:

* **v1 never auto-confirms.** Confidence is hard-capped at 0.75 against a
  0.85 confirm threshold, so every v1 match lands in a review queue and no
  score changes automatically. Auto-confirm needs image evidence, which v1
  does not have — the cap makes that structural, not a tuning choice.
* **Price ratio is a veto, never evidence.** A retail/cost ratio outside
  1.5-15x kills the match; a plausible ratio alone never creates one.
* **Shared tokens must be distinctive.** "Premium Pet Bed" and "new pet bed"
  share 100% of their content words and mean nothing. Category words are
  derived from the supplier corpus by document frequency rather than a
  hand-curated list, so the notion tracks your catalogue.
* **Evidence is stored on every match** — shared tokens, scores, the
  translated title. A bad margin months from now has to be debuggable.
* Rejecting a match is sticky: re-running refreshes scores but never
  resurrects a pair a human already rejected.

Supplier titles are translated once via Claude (batched ~40 per call, cached
on the row, needs `ANTHROPIC_API_KEY`) because 1688 titles are Chinese and
keyword-stuffed. Without translation there is no text signal and nothing
matches.

> **Thresholds are provisional.** They are tuned against realistic fixtures,
> not measured precision. The review queue exists partly to produce that
> measurement before v2 raises confidence high enough to auto-apply margins.

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
