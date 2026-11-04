-- Signup funnel (app/funnel.py): landing visit -> signup click -> account ->
-- first winner opened -> checkout started -> paid, split by language.
--
-- Anonymous rows (landing_view, signup_click) carry no user id, cookie or IP:
-- only the event, the page language and which button. Account milestones
-- carry the user id and are recorded once per user.
create table if not exists funnel_events (
  id         bigserial primary key,
  event      text not null,
  user_id    uuid,
  lang       text,
  source     text,
  created_at timestamptz not null default now()
);
create index if not exists funnel_events_event_time on funnel_events (event, created_at);
create unique index if not exists funnel_events_once_per_user on funnel_events (user_id, event)
  where user_id is not null;
alter table funnel_events enable row level security;
