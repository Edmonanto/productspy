-- Allow a third pick tier: "watch" (best of the rest when fewer than 5
-- products reach 60 — early signals with thin evidence).
alter table daily_winners drop constraint if exists daily_winners_tier_check;
alter table daily_winners add constraint daily_winners_tier_check
    check (tier in ('winner', 'rising', 'watch'));
