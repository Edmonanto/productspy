# ProductSpy Pro — API

FastAPI backend for the Next.js frontend in the repo root. Mounted at
`/api/v1` to match the frontend's `NEXT_PUBLIC_API_URL`.

**Product data comes from 1688.com only**, through two hosted endpoints
(keyword search and item detail), each with its own metered token.

## Layout

```
app/
  main.py              FastAPI app, CORS, router mounting
  config.py            all settings (env vars) incl. 1688 tokens, TTLs, seed keywords
  auth.py              Supabase JWT verification
  routers/             HTTP layer only — products, watchlist, users, billing
  services/catalog.py  cache-first flow: search cache -> 1688 -> ingest -> score
  sources/ali1688/     the only code that knows the 1688 payload shape
    client.py          HTTP + error envelope ({"code":"error","msg":...})
    parser.py          raw JSON -> models (pure, fixture-tested)
    models.py          SearchOffer, OfferDetail, Seller, PriceTier
  repository.py        plain SQL (asyncpg), no ORM
  scoring.py           1688-signal scoring (pure)
  quota.py             per-plan search / watchlist limits
  worker.py            ingest job: `python -m app.worker`
migrations/            run in order: 001_init.sql, 002_ali1688.sql
tests/fixtures/        real (trimmed) 1688 search + detail responses
```

## How 1688 data flows

| Trigger | 1688 call | Cached for |
| --- | --- | --- |
| `GET /products/search?q=衣服&page=1` | 1 search call per (keyword, page) | `SEARCH_CACHE_TTL_HOURS` (12h) |
| `GET /products/{id}` opened | 1 detail call when stored detail is stale | `DETAIL_CACHE_TTL_HOURS` (72h) |
| `GET /products/{1688 offer id}` | 1 detail call, imports the product | same |
| `python -m app.worker` (daily cron) | 1 search per seed keyword | same as search |
| `GET /products/trending` | none — reads Postgres | — |

Every ingested offer is upserted into `products` (keyed by `source='1688'`,
`external_id=offerId`), gets a `suppliers` row for its 1688 seller, and a
`product_snapshots` row for today's sales count. It is then scored.

If 1688 fails (network, bad token, out of credits), search returns **502** and
the user's daily quota is **not** charged; product pages fall back to the
stored copy.

**Prices:** 1688 is CNY wholesale. `cost_usd` = price × `CNY_TO_USD`;
`price_usd` is a *suggested* resale price = cost × `RETAIL_MARKUP` (3×).

**Keywords:** 1688 search is Chinese-language. English queries return poor
results; translating user queries is a planned next step.

## Scoring

All 0-100, higher is better (`app/scoring.py`):

- **demand** (35%) — log-scaled units sold (100 → 40, 10k → 80, 100k → 100),
  plus repurchase rate
- **margin** (25%) — resale headroom from unit cost: ≤$2 → 100, ≥$40 → 0
- **trend** (25%) — weekly sales growth between daily snapshots; stays at a
  neutral 50 until a product has 2+ days of history
- **competition** (15%) — inverted ad volume; neutral 50 with no ad data

`ai_summary` currently holds a factual one-liner
("7,900+ sold on 1688 · 12% repurchase rate · $3.92 unit cost · ships from …").

## Running locally

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt pytest
cp .env.example .env        # DATABASE_URL, SUPABASE_JWT_SECRET, both 1688 tokens
psql "$DATABASE_URL" -f migrations/001_init.sql
psql "$DATABASE_URL" -f migrations/002_ali1688.sql
uvicorn app.main:app --reload --port 8000
python -m app.worker        # fill /products/trending once
```

Interactive docs at http://localhost:8000/docs, health at `/health`.

## Tests

```bash
pytest tests/ -q
```

No Postgres and no 1688 calls: the DB layer is stubbed and parsing runs
against the captured fixtures.

## Deploying on Render

The repo root has a `render.yaml` Blueprint: API + frontend web services and
a daily ingest cron, all in Singapore (closest Render region to the 1688
endpoints). Postgres stays on Supabase.

1. Run both migrations against Supabase (SQL editor, or `psql` as above).
2. Render dashboard → **New → Blueprint** → select this GitHub repo.
3. Fill in the prompted secrets: `DATABASE_URL` (Supabase *pooler* URI),
   `SUPABASE_JWT_SECRET`, `ALI1688_SEARCH_TOKEN`, `ALI1688_DETAIL_TOKEN`,
   `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, and
   `NEXT_PUBLIC_API_URL` = `https://productspy-api.onrender.com/api/v1`.
4. After the first deploy, check `https://productspy-api.onrender.com/health`
   shows `"database": true`, then trigger the `productspy-ingest` cron once
   by hand so trending has data.
5. Custom domain: add `productspy.pro` to `productspy-web` (Settings →
   Custom Domains) and point DNS as Render instructs. Add the domain in
   Supabase → Auth → URL Configuration too.

Free web services sleep after 15 idle minutes (first request then takes
~30s). Move `productspy-api` to *starter* before real users arrive. Cron jobs
need a paid plan.

## Endpoint status

| Endpoint | Status |
| --- | --- |
| `GET /users/me` | done — profile, subscription, live quota |
| `GET /products/trending` | done — stored 1688 products; filters by category, min_score |
| `GET /products/search` | done — live 1688 search, cached; charges daily quota (429 when spent, 502 + no charge on upstream failure) |
| `GET /products/{id}` | done — uuid or 1688 offer id; refreshes 1688 detail when stale |
| `POST /products/{id}/rescore` | done |
| `GET /watchlist/` `POST` `DELETE` | done — free plan capped at 10; POST accepts a 1688 offer id |
| `GET /billing/status` | done — reads real subscription rows |
| `POST /billing/checkout` `portal` `cancel` | **501** — Phase 3 |

## Remaining work

- **Keyword translation** — English → Chinese before hitting 1688 search.
- **Ad / competition data** — 1688 has none; competition stays neutral until
  an ad-signal source is added.
- **Phase 3 — billing.** Stripe/PayPal checkout, portal and webhooks. Plans
  and quotas are already in `app/config.py`.
