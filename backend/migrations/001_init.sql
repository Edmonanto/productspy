-- ProductSpy Pro — initial schema
-- Runs against the same Supabase Postgres the frontend authenticates with.
-- User identity lives in Supabase's auth.users; we only store the uuid.

create extension if not exists "pgcrypto";

-- ── Products ────────────────────────────────────────────────────────────────
create table if not exists products (
    id           uuid primary key default gen_random_uuid(),
    title        text        not null,
    image_url    text,
    product_url  text        not null,
    category     text,
    price_usd    numeric(10, 2),
    cost_usd     numeric(10, 2),
    source       text        not null,           -- aliexpress | amazon | tiktok | ...
    external_id  text,                           -- id on the source platform
    first_seen_at timestamptz not null default now(),
    updated_at   timestamptz not null default now(),
    unique (source, external_id)
);

create index if not exists products_category_idx on products (category);
create index if not exists products_source_idx   on products (source);
-- trigram index powers /products/search without a full table scan
create extension if not exists pg_trgm;
create index if not exists products_title_trgm_idx on products using gin (title gin_trgm_ops);

-- ── Scores (one current row per product) ────────────────────────────────────
create table if not exists product_scores (
    product_id        uuid primary key references products (id) on delete cascade,
    overall_score     int not null check (overall_score     between 0 and 100),
    demand_score      int not null check (demand_score      between 0 and 100),
    margin_score      int not null check (margin_score      between 0 and 100),
    competition_score int not null check (competition_score between 0 and 100),
    trend_score       int not null check (trend_score       between 0 and 100),
    ai_summary        text not null default '',
    scored_at         timestamptz not null default now()
);

create index if not exists product_scores_overall_idx on product_scores (overall_score desc);

-- ── Suppliers ───────────────────────────────────────────────────────────────
create table if not exists suppliers (
    id             uuid primary key default gen_random_uuid(),
    product_id     uuid not null references products (id) on delete cascade,
    platform       text not null,
    supplier_name  text not null,
    supplier_url   text not null,
    unit_cost_usd  numeric(10, 2) not null default 0,
    shipping_days  int            not null default 0,
    rating         numeric(3, 2)  not null default 0
);

create index if not exists suppliers_product_idx on suppliers (product_id);

-- ── Ad signals (time series; trend/competition are derived from these) ──────
create table if not exists ad_signals (
    id           uuid primary key default gen_random_uuid(),
    product_id   uuid not null references products (id) on delete cascade,
    platform     text not null,                  -- tiktok | facebook | ...
    ad_count     int  not null default 0,
    last_seen_at timestamptz not null default now(),
    unique (product_id, platform)
);

create index if not exists ad_signals_product_idx on ad_signals (product_id);

-- ── Watchlist ───────────────────────────────────────────────────────────────
create table if not exists watchlists (
    id         uuid primary key default gen_random_uuid(),
    user_id    uuid not null,                    -- auth.users.id
    product_id uuid not null references products (id) on delete cascade,
    added_at   timestamptz not null default now(),
    unique (user_id, product_id)
);

create index if not exists watchlists_user_idx on watchlists (user_id);

-- ── Subscriptions ───────────────────────────────────────────────────────────
create table if not exists subscriptions (
    user_id             uuid primary key,
    plan                text not null default 'free',    -- free|starter|pro|agency
    status              text not null default 'active',  -- active|past_due|canceled
    provider            text not null default 'none',    -- stripe|paypal|none
    provider_customer_id     text,
    provider_subscription_id text,
    current_period_end  timestamptz,
    updated_at          timestamptz not null default now()
);

-- ── Search quota usage (per user per UTC day) ───────────────────────────────
create table if not exists search_usage (
    user_id   uuid not null,
    usage_day date not null default (now() at time zone 'utc')::date,
    used      int  not null default 0,
    primary key (user_id, usage_day)
);
