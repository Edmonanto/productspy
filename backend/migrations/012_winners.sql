-- Phase 5 — Daily Winners.
-- (First shipped as 007_winners.sql; renumbered after GitHub's
-- 007-011. Idempotent, so databases that ran it under the old name are fine.)
-- A second engine beside ingestion: instead of marketplace listings, it reads
-- *advertising* (Facebook Ad Library, TikTok Creative Center) and TikTok
-- videos per market, groups the ads into products, scores them, and picks the
-- 5-10 strongest per market per day.
--
-- Products found this way live in `products` with source = 'winners' and
-- external_id = a canonical product key ("posture-corrector"), so the watchlist
-- and product pages work for them unchanged.

-- Risk flags and ratings the extraction step assigns (wow, problem, ip_risk,
-- restricted, fragile_heavy, seasonal, est_cost_usd).
alter table products add column if not exists attributes jsonb not null default '{}'::jsonb;
-- cost_usd came from an AI estimate, not a supplier listing. Scored 20% lower.
alter table products add column if not exists cost_estimated boolean not null default false;

-- ── Ad creatives: every ad / video seen, per market ─────────────────────────
create table if not exists ad_creatives (
    id               uuid primary key default gen_random_uuid(),
    platform         text        not null,       -- meta | tiktok_ads | tiktok_organic
    external_id      text        not null,
    market           text        not null,       -- US | UK | EU | AU | AE | CA | FR | DE | SA
    product_id       uuid references products (id) on delete set null,
    advertiser_name  text,
    advertiser_id    text,
    ad_text          text,
    landing_url      text,
    landing_domain   text,
    media_url        text,
    thumbnail_url    text,
    ad_url           text,
    started_at       timestamptz,                -- ad start date / video post date
    last_seen_at     timestamptz not null default now(),
    is_active        boolean     not null default true,
    variant_count    int         not null default 1,   -- "N ads use this creative"
    reach            bigint,                     -- EU reach (Meta DSA data)
    views            bigint,
    likes            bigint,
    comments         bigint,
    shares           bigint,
    ctr              numeric(6, 4),              -- 0.0312 = 3.12 %
    budget_level     int,                        -- TikTok Creative Center 1..5
    intent_comments  int,                        -- "where can I buy" in the sample
    sampled_comments int,
    not_product      boolean     not null default false,  -- extraction said: no single product
    raw              jsonb       not null default '{}'::jsonb,
    created_at       timestamptz not null default now(),
    unique (platform, external_id, market)
);

create index if not exists ad_creatives_product_idx on ad_creatives (product_id);
create index if not exists ad_creatives_market_seen_idx on ad_creatives (market, last_seen_at desc);
create index if not exists ad_creatives_unlinked_idx
    on ad_creatives (market) where product_id is null and not_product = false;

-- ── Winner scores: one row per product per market per day ──────────────────
create table if not exists winner_scores (
    id           uuid primary key default gen_random_uuid(),
    product_id   uuid        not null references products (id) on delete cascade,
    market       text        not null,
    scored_on    date        not null default (now() at time zone 'utc')::date,
    total        int         not null check (total between 0 and 100),
    breakdown    jsonb       not null,           -- {scaling, engagement, demand, margin, freshness}
    penalties    jsonb       not null default '[]'::jsonb,
    reasons      jsonb       not null default '[]'::jsonb,
    signals      jsonb       not null default '{}'::jsonb,
    confidence   text,                           -- low | medium | high
    excluded     text,                           -- why it was hard-filtered, if it was
    created_at   timestamptz not null default now(),
    unique (product_id, market, scored_on)
);

create index if not exists winner_scores_market_day_idx
    on winner_scores (market, scored_on desc, total desc);

-- ── Daily winners: the picks ────────────────────────────────────────────────
create table if not exists daily_winners (
    id          uuid primary key default gen_random_uuid(),
    market      text        not null,
    pick_date   date        not null,
    rank        int         not null,
    tier        text        not null default 'winner' check (tier in ('winner', 'rising')),
    product_id  uuid        not null references products (id) on delete cascade,
    score_id    uuid references winner_scores (id) on delete set null,
    total       int         not null,
    created_at  timestamptz not null default now(),
    unique (market, pick_date, product_id),
    unique (market, pick_date, rank)
);

create index if not exists daily_winners_market_day_idx on daily_winners (market, pick_date desc, rank);

-- ── Run log (shown on the dashboard, and the first place to look) ──────────
create table if not exists winner_runs (
    id           bigserial primary key,
    market       text        not null,
    started_at   timestamptz not null default now(),
    finished_at  timestamptz,
    status       text        not null default 'running',  -- running | ok | partial | failed
    stats        jsonb       not null default '{}'::jsonb,
    errors       jsonb       not null default '[]'::jsonb
);

create index if not exists winner_runs_market_idx on winner_runs (market, started_at desc);

-- ── Which markets each user follows ─────────────────────────────────────────
create table if not exists user_preferences (
    user_id     uuid primary key,                -- auth.users.id
    markets     text[]      not null default array['US'],
    updated_at  timestamptz not null default now()
);
