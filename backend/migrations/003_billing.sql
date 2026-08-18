-- Phase 3 — billing.
-- Subscriptions already exist (001); this adds the provider plumbing and the
-- webhook ledger that makes delivery idempotent.

alter table subscriptions add column if not exists cancel_at_period_end boolean not null default false;
alter table subscriptions add column if not exists updated_at timestamptz not null default now();

-- Look up a subscription by what the provider sends us in a webhook.
create index if not exists subscriptions_provider_customer_idx
    on subscriptions (provider_customer_id);
create index if not exists subscriptions_provider_subscription_idx
    on subscriptions (provider_subscription_id);

-- ── Webhook ledger ──────────────────────────────────────────────────────────
-- Stripe and PayPal both retry on non-2xx and can deliver the same event more
-- than once. The unique key makes replays a no-op instead of a double upgrade.
create table if not exists billing_events (
    id           bigserial primary key,
    provider     text        not null,      -- stripe | paypal
    event_id     text        not null,      -- provider's own event id
    event_type   text        not null,
    received_at  timestamptz not null default now(),
    processed_at timestamptz,
    error        text,
    unique (provider, event_id)
);

create index if not exists billing_events_received_idx on billing_events (received_at desc);
