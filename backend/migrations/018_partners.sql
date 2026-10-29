-- Coach / partner referral program.
--
-- A partner shares productspy.pro/?ref=CODE. Visitors who sign up through it are
-- attributed to the partner (first touch, 30-day window), get the partner
-- discount on their first paid month, and every payment they make in the next
-- commission_months earns the partner commission_pct. Commissions wait
-- HOLD_DAYS (refund window) before they can be paid out.

create table if not exists affiliates (
    id                uuid primary key default gen_random_uuid(),
    user_id           uuid unique,                       -- the partner's own account, once linked
    name              text not null,
    email             text not null,
    code              text not null unique,              -- upper-case, A-Z 0-9 _ -
    commission_pct    numeric not null default 30 check (commission_pct between 0 and 90),
    commission_months int     not null default 12 check (commission_months between 1 and 120),
    discount_pct      numeric not null default 25 check (discount_pct between 0 and 90),
    status            text not null default 'active' check (status in ('active', 'paused')),
    payout_method     text check (payout_method in ('paypal', 'wise', 'bank', 'other')),
    payout_details    text not null default '',
    clicks            int not null default 0,
    created_at        timestamptz not null default now()
);
create index if not exists affiliates_email on affiliates (lower(email));

-- One row per referred customer (first touch wins).
create table if not exists referrals (
    user_id        uuid primary key,
    affiliate_id   uuid not null references affiliates (id) on delete cascade,
    code           text not null,
    created_at     timestamptz not null default now(),
    first_paid_at  timestamptz
);
create index if not exists referrals_affiliate on referrals (affiliate_id);

-- One row per paid invoice of a referred customer.
create table if not exists commissions (
    id              uuid primary key default gen_random_uuid(),
    affiliate_id    uuid not null references affiliates (id) on delete cascade,
    user_id         uuid not null,
    provider        text not null,                 -- stripe | paypal
    invoice_id      text not null,
    amount          numeric not null,              -- what the customer paid (excl. tax), in currency
    commission      numeric not null,
    currency        text not null default 'usd',
    status          text not null default 'pending' check (status in ('pending', 'paid', 'void')),
    created_at      timestamptz not null default now(),
    paid_at         timestamptz,
    payout_ref      text,
    unique (provider, invoice_id)
);
create index if not exists commissions_affiliate on commissions (affiliate_id, created_at desc);
