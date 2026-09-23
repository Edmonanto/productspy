-- Phase 4 — cross-platform matching (v1).
-- Links a retail listing (TikTok/Amazon: real price, no cost) to a supplier
-- listing (1688: real cost, no retail) so margin can be computed from two
-- observed numbers instead of a markup guess.
--
-- Nothing here changes a score on its own. A match only affects margin once
-- it is `confirmed`, and v1 never auto-confirms — see app/matching/.

-- Cached English rendering of a non-English title. Titles don't change, so
-- this is translated once per product and reused forever.
alter table products add column if not exists title_en text;
alter table products add column if not exists translated_at timestamptz;

create table if not exists product_matches (
    id           bigserial primary key,
    -- The listing we know a real retail price for.
    retail_id    uuid        not null references products (id) on delete cascade,
    -- The listing we know a real supplier cost for.
    supplier_id  uuid        not null references products (id) on delete cascade,
    confidence   numeric(3, 2) not null check (confidence between 0 and 1),
    method       text        not null,          -- title | price | title+price
    -- Why this matched: shared tokens, scores, the translated title. Without
    -- it a bad margin months later is undebuggable.
    evidence     jsonb       not null default '{}'::jsonb,
    status       text        not null default 'candidate'
                 check (status in ('candidate', 'confirmed', 'rejected')),
    created_at   timestamptz not null default now(),
    reviewed_at  timestamptz,
    unique (retail_id, supplier_id)
);

create index if not exists product_matches_retail_idx on product_matches (retail_id);
create index if not exists product_matches_supplier_idx on product_matches (supplier_id);
-- The review queue reads this: best candidates first.
create index if not exists product_matches_status_conf_idx
    on product_matches (status, confidence desc);
