-- Metered-API accounting.
--
-- The 1688 tokens are prepaid per call and gave no warning before running
-- dry: the provider answered "token次数不足" (out of credits), the worker
-- logged it and carried on, and the run log recorded no error at all. This
-- table makes every paid call visible, enforces a daily cap, and remembers
-- when a token ran out so /status can say so.

create table if not exists api_usage (
    provider          text not null,              -- 1688-aggregator, ...
    endpoint          text not null,              -- search | detail
    usage_day         date not null default (now() at time zone 'utc')::date,
    calls             int  not null default 0,    -- every request sent, success or not
    failures          int  not null default 0,
    last_balance      int,                        -- calls left, when the provider reports it
    last_error        text,
    out_of_credits_at timestamptz,
    updated_at        timestamptz not null default now(),
    primary key (provider, endpoint, usage_day)
);
