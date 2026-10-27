-- AI research reports, validation workflow, usage metering.

-- One AI research report per product + market + evidence snapshot. Cached:
-- the same evidence (evidence_hash) is never sent to the AI twice.
create table if not exists product_reports (
    id             uuid primary key default gen_random_uuid(),
    product_id     uuid not null references products (id) on delete cascade,
    market         text not null,
    evidence_hash  text not null,
    status         text not null default 'pending' check (status in ('pending', 'ready', 'failed')),
    report         jsonb,
    warnings       jsonb not null default '[]'::jsonb,
    model          text,
    tokens_in      int,
    tokens_out     int,
    error          text,
    requested_by   uuid,
    created_at     timestamptz not null default now(),
    finished_at    timestamptz
);
create index if not exists product_reports_lookup on product_reports (product_id, market, created_at desc);

-- Who asked for a (non-cached) report and when — enforces reports_per_day.
create table if not exists report_requests (
    user_id     uuid not null,
    report_id   uuid references product_reports (id) on delete set null,
    created_at  timestamptz not null default now()
);
create index if not exists report_requests_user_day on report_requests (user_id, created_at desc);

-- Validation workflow for a saved product: one row per user + product + stage.
create table if not exists validation_steps (
    user_id     uuid not null,
    product_id  uuid not null references products (id) on delete cascade,
    stage       text not null,
    status      text not null default 'not_started'
                check (status in ('not_started', 'in_progress', 'completed', 'blocked')),
    notes       text not null default '',
    links       jsonb not null default '[]'::jsonb,
    updated_at  timestamptz not null default now(),
    primary key (user_id, product_id, stage)
);

-- The user's real numbers for a product: supplier quote, test spend, orders.
create table if not exists validation_results (
    user_id            uuid not null,
    product_id         uuid not null references products (id) on delete cascade,
    supplier_quote_usd numeric,
    shipping_quote_usd numeric,
    selling_price_usd  numeric,
    ad_spend_usd       numeric,
    orders             int,
    revenue_usd        numeric,
    refunds            int,
    decision           text check (decision in ('launch', 'iterate', 'drop')),
    updated_at         timestamptz not null default now(),
    primary key (user_id, product_id)
);

-- Metering of paid APIs (app/usage.py). 014 dropped the old 1688-era table,
-- so it is (re)created here; the alters cover a database that still has it.
create table if not exists api_usage (
    provider          text not null,
    endpoint          text not null,
    usage_day         date not null default (now() at time zone 'utc')::date,
    calls             int  not null default 0,
    failures          int  not null default 0,
    tokens_in         bigint not null default 0,
    tokens_out        bigint not null default 0,
    items             bigint not null default 0,
    last_balance      int,
    last_error        text,
    out_of_credits_at timestamptz,
    updated_at        timestamptz not null default now(),
    primary key (provider, endpoint, usage_day)
);
alter table api_usage add column if not exists tokens_in bigint not null default 0;
alter table api_usage add column if not exists tokens_out bigint not null default 0;
alter table api_usage add column if not exists items bigint not null default 0;
