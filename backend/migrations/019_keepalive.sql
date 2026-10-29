-- Keep the free Render API awake: Render puts a free web service to sleep after
-- 15 minutes without traffic, and the next visitor waits ~50 s. Supabase's own
-- scheduler (pg_cron) calls /health every 10 minutes through pg_net — free, no
-- outside service. 144 tiny requests a day; one service awake 24/7 fits in
-- Render's 750 free hours a month.
--
-- Never blocks startup: if the extensions aren't available (local Postgres,
-- tests), it logs a notice and moves on.
do $outer$
begin
  create extension if not exists pg_net;
  create extension if not exists pg_cron;
  perform cron.unschedule(jobid) from cron.job where jobname = 'productspy-keepalive';
  perform cron.schedule(
    'productspy-keepalive',
    '*/10 * * * *',
    $job$select net.http_get('https://productspy-api.onrender.com/health')$job$
  );
exception when others then
  raise notice 'keep-alive not scheduled: %', sqlerrm;
end
$outer$;
