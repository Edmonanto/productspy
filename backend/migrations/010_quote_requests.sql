-- Quote requests: a customer asks for an exact price (unit cost, shipping to
-- their country) on a product instead of relying on the calculator's
-- estimate. Admins (ADMIN_EMAILS) answer them from /dashboard/quotes.

create table if not exists quote_requests (
    id                  uuid primary key default gen_random_uuid(),
    user_id             uuid        not null,          -- auth.users.id
    user_email          text        not null default '',
    product_id          uuid        references products (id) on delete set null,
    -- Copied at request time so the quote still reads correctly if the
    -- product row is later refreshed or removed.
    product_title       text        not null default '',
    quantity            int         not null check (quantity > 0),
    destination_country text        not null,
    target_price_usd    numeric(10, 2),
    notes               text        not null default '',
    status              text        not null default 'open'
                        check (status in ('open', 'quoted', 'closed')),
    quoted_unit_usd     numeric(10, 2),
    quoted_shipping_usd numeric(10, 2),
    reply               text        not null default '',
    created_at          timestamptz not null default now(),
    replied_at          timestamptz
);

create index if not exists quote_requests_user_idx on quote_requests (user_id, created_at desc);
create index if not exists quote_requests_status_idx on quote_requests (status, created_at desc);
