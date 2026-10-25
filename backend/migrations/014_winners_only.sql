-- Phase 7 — ProductSpy Pro is Daily Winners only.
--
-- The marketplace engine (TikTok Shop / 1688 / Amazon ingestion, trend
-- snapshots, search quotas, retail-to-supplier matching) was removed from the
-- code. This deletes its data for good:
--
--   * every product that did not come from the Daily Winners engine — with
--     its suppliers, ad signals and watchlist entries (on delete cascade);
--   * the tables only that engine used.
--
-- Quote requests (010) stay: they are product-agnostic, and a request about a
-- deleted product keeps its copied title (product_id is set to null).
--
-- Numbered after GitHub's 007-011 so a fresh database applies them first
-- (011 alters product_scores, which this drops). Databases that already ran
-- this as 009_winners_only re-run it harmlessly: nothing left to delete.
--
-- Irreversible. Take a Supabase backup first if you might want the old
-- catalogue back. Safe to re-run: the second run finds nothing to delete.

delete from products where source <> 'winners';

drop table if exists api_usage;            -- 1688 call metering (007)
drop table if exists product_matches;
drop table if exists product_snapshots;
drop table if exists ingestion_runs;
drop table if exists search_usage;
drop table if exists product_scores;
