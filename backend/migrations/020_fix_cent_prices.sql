-- Prices scraped in cents (6400 for $64.00) made some products look hugely
-- profitable. The scraper now catches this (enrich.sane_price); this fixes the
-- prices already saved. Dropshipping products sell far below $1,000, so a
-- stored price that high is read as cents when that gives a normal price,
-- and otherwise cleared so the next scan fetches it again.
update products
   set price_usd = round(price_usd / 100, 2), updated_at = now()
 where price_usd >= 1000 and price_usd / 100 between 3 and 500;

update products
   set price_usd = null, updated_at = now()
 where price_usd >= 1000;
