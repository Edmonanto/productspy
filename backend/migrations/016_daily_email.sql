-- Daily winners email: on by default, one-click unsubscribe, one per day.
alter table user_preferences add column if not exists email_digest boolean not null default true;
alter table user_preferences add column if not exists digest_sent_on date;
