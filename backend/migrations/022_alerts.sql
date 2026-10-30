-- Failure alerts (app/alerts.py). alerts_sent keeps the watchdog to one email
-- a day; pg_cron calls the watchdog at 03:30 UTC, 2.5 hours after the nightly
-- scan (01:00 UTC) — it emails the owner if a market has no finished scan.
create table if not exists alerts_sent (
  kind    text not null,
  day     date not null,
  sent_at timestamptz not null default now(),
  primary key (kind, day)
);
alter table alerts_sent enable row level security;

do $outer$
begin
  create extension if not exists pg_net;
  create extension if not exists pg_cron;
  perform cron.unschedule(jobid) from cron.job where jobname = 'productspy-watchdog';
  perform cron.schedule(
    'productspy-watchdog',
    '30 3 * * *',
    $job$select net.http_get('https://productspy-api.onrender.com/api/v1/winners/watchdog', timeout_milliseconds => 60000)$job$
  );
exception when others then
  raise notice 'watchdog not scheduled: %', sqlerrm;
end
$outer$;
