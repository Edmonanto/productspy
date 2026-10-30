-- Product photos stored by us (app/winners/photos.py). Ad thumbnails from
-- Facebook/TikTok are signed links that expire after a few days; each pick's
-- photo is checked (the AI confirms it shows the product), shrunk to a small
-- JPEG (~40 KB) and served from /api/v1/images/<product id>.jpg.
create table if not exists product_images (
  product_id   uuid primary key references products(id) on delete cascade,
  data         bytea not null,
  content_type text not null default 'image/jpeg',
  source_url   text,
  ai_checked   boolean not null default false,
  updated_at   timestamptz not null default now()
);

alter table product_images enable row level security;
