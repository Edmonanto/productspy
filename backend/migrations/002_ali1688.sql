-- 1688 becomes the only product source.
-- Adds the raw 1688 signals scoring uses, a sales time series for trend, and
-- a search cache so repeated keywords do not spend metered API calls.
-- Idempotent: safe to run more than once.

-- ── Products: 1688 fields ───────────────────────────────────────────────────
alter table products add column if not exists price_cny        numeric(12, 2);
alter table products add column if not exists sales_count      int;
alter table products add column if not exists repurchase_rate  numeric(5, 4);  -- 0.12 = 12%
alter table products add column if not exists is_ad            boolean not null default false;
alter table products add column if not exists images           text[]  not null default '{}';
alter table products add column if not exists details          jsonb   not null default '{}'::jsonb;
alter table products add column if not exists detail_fetched_at timestamptz;

create index if not exists products_updated_idx on products (updated_at desc);

-- One supplier row per product and platform, so ingest can upsert it.
create unique index if not exists suppliers_product_platform_uidx
    on suppliers (product_id, platform);

-- ── Sales snapshots (trend is derived from growth between these) ────────────
create table if not exists product_snapshots (
    product_id  uuid        not null references products (id) on delete cascade,
    captured_on date        not null default (now() at time zone 'utc')::date,
    sales_count int,
    price_cny   numeric(12, 2),
    primary key (product_id, captured_on)
);

-- ── Search cache (keyword + page -> ordered offer ids) ──────────────────────
create table if not exists search_cache (
    keyword     text        not null,
    page        int         not null,
    total_found int         not null default 0,
    has_more    boolean     not null default false,
    offer_ids   text[]      not null default '{}',
    fetched_at  timestamptz not null default now(),
    primary key (keyword, page)
);
