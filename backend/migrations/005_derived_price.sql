-- A retail price we computed is not a retail price we observed.
--
-- 1688 publishes wholesale cost and no retail price, so ingestion derives one
-- as cost * WHOLESALE_MARKUP. Margin then reduces to (m-1)/m for every such
-- row — a restatement of the config constant, identical across the catalogue,
-- carrying no information about the product. Scored as if observed it awarded
-- every 1688 listing margin 95/100 and 30% of the composite weight, which put
-- untranslated supplier listings at the top of Trending ahead of real retail
-- winners.
--
-- Flag the provenance so scoring can treat a derived price as an unknown
-- margin rather than an excellent one. Real margin arrives through a confirmed
-- match, which pairs an observed retail price with an observed supplier cost.

alter table products add column if not exists price_is_derived boolean not null default false;

-- Every 1688 price already in the table came from the markup.
update products set price_is_derived = true
 where source = '1688' and price_usd is not null and price_is_derived = false;

comment on column products.price_is_derived is
    'true when price_usd was computed from cost (not published by the source); '
    'margin scoring treats such a price as unknown.';
