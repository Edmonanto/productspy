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
-- Irreversible. Take a Supabase backup first if you might want the old
-- catalogue back. Safe to re-run: the second run finds nothing to delete.

delete from products where source <> 'winners';

drop table if exists product_matches;
drop table if exists product_snapshots;
drop table if exists ingestion_runs;
drop table if exists search_usage;
drop table if exists product_scores;
