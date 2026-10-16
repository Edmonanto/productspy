-- Sourcing detail for the product page: tiered prices, MOQ, weight, where it
-- ships from, the seller, gallery and variants. Fetched from the 1688 detail
-- endpoint the first time a product page is opened, then cached here for
-- DETAIL_TTL_DAYS so repeat views cost no prepaid calls.

alter table products add column if not exists details jsonb;
alter table products add column if not exists details_fetched_at timestamptz;
