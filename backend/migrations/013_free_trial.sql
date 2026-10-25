-- Phase 6 — 7-day free trial, no card.
-- (First shipped as 008_free_trial.sql; renumbered after GitHub's
-- 007-011. Idempotent, so databases that ran it under the old name are fine.)
--
-- A new account's first subscription row is written with status 'trialing'
-- and plan = TRIAL_PLAN. Provider stays 'none', which is what distinguishes
-- an app trial from a paid subscription: Stripe and PayPal webhooks always
-- write their own provider (and Stripe maps its own 'trialing' to 'active').
--
-- Access is decided at read time by app/trial.py — a trial whose
-- trial_ends_at has passed counts as Free immediately, even before the daily
-- job rewrites the row.

alter table subscriptions add column if not exists trial_started_at timestamptz;
alter table subscriptions add column if not exists trial_ends_at timestamptz;
-- One trial per account, ever.
alter table subscriptions add column if not exists trial_used boolean not null default false;
alter table subscriptions add column if not exists trial_reminder_sent_at timestamptz;
-- The address trial reminders go to. Identity lives in Supabase auth; this is
-- copied from the access token when the row is created.
alter table subscriptions add column if not exists email text;

create index if not exists subscriptions_trial_end_idx
    on subscriptions (trial_ends_at)
    where status = 'trialing' and provider = 'none';
