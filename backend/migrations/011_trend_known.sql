-- Whether trend_score was measured or defaulted. Without history a product's
-- trend is the neutral 50 — indistinguishable from genuinely flat sales — so
-- the UI couldn't say "new, still collecting data". This flag says it.
--
-- Guarded: product_scores belonged to the marketplace engine and is dropped
-- by 014_winners_only (first shipped as 009_winners_only, which may already
-- have run on a database that never applied this file). Skipping when the
-- table is gone keeps startup migrations from failing there.

do $$
begin
    if to_regclass('product_scores') is not null then
        alter table product_scores add column if not exists trend_known boolean not null default false;
    end if;
end
$$;
