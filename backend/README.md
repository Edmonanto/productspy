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
| `POST /products/{id}/rescore` | partial — recomputes margin + competition (see below) |
| `GET /watchlist/` `POST` `DELETE` | done — free plan capped at 10 |
| `GET /billing/status` | done — reads real subscription rows |
| `POST /billing/checkout` `portal` `cancel` | **501** — Phase 3 |

## Scoring

`app/scoring.py` computes what is derivable from stored data today:

- **margin** — gross margin from `price_usd` vs `cost_usd`; 70%+ saturates at 100.
- **competition** — inverted ad volume (few advertisers scores high); no data
  returns a neutral 50 rather than falsely claiming an open market.

**demand** and **trend** need time-series signals that the Phase 2 ingestion
worker will collect, so `rescore` preserves existing values instead of
inventing them. `ai_summary` is likewise left to Phase 2.

## Remaining work

**Phase 2 — ingestion & scoring.** A scheduled worker that pulls products,
upserts them, records `ad_signals` over time, then derives demand/trend and
writes an `ai_summary`. Note that scraping AliExpress/Amazon/TikTok directly is
brittle and against their terms; prefer official/affiliate APIs or a licensed
data provider.

**Phase 3 — billing.** Stripe and PayPal checkout, a customer portal, and
`POST /billing/webhook/{provider}` to keep `subscriptions` in sync. The four
plans (`free`, `starter` $29, `pro` $79, `agency` $199) and their quotas are
already defined in `app/config.py`.
