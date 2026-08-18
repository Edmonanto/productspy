-- Phase 2 — ingestion + time-series signals.
-- trend_score is derived from our own snapshot history, not bought from a
-- provider, so this table is the asset: it only becomes useful once the
-- worker has been running for a couple of weeks.

alter table products add column if not exists orders_count int;
alter table products add column if not exists rating numeric(3, 2);
alter table products add column if not exists provider text;

-- ── Snapshots (one row per product per ingestion run) ───────────────────────
create table if not exists product_snapshots (
    id            bigserial primary key,
    product_id    uuid        not null references products (id) on delete cascade,
    captured_at   timestamptz not null default now(),
    price_usd     numeric(10, 2),
    cost_usd      numeric(10, 2),
    orders_count  int,
    ad_count      int
);

-- Trend lookups always ask "this product, around N days ago".
create index if not exists product_snapshots_product_time_idx
    on product_snapshots (product_id, captured_at desc);

-- ── Ingestion run log (observability for the cron job) ──────────────────────
create table if not exists ingestion_runs (
    id           bigserial primary key,
    provider     text        not null,
    started_at   timestamptz not null default now(),
    finished_at  timestamptz,
    fetched      int         not null default 0,
    upserted     int         not null default 0,
    scored       int         not null default 0,
    summarized   int         not null default 0,
    error        text
);

create index if not exists ingestion_runs_started_idx on ingestion_runs (started_at desc);
