-- Whether trend_score was measured or defaulted. Without history a product's
-- trend is the neutral 50 — indistinguishable from genuinely flat sales — so
-- the UI couldn't say "new, still collecting data". This flag says it.

alter table product_scores add column if not exists trend_known boolean not null default false;
