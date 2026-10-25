-- English search over translated 1688 titles.
-- /products/search matches each query word against title_en with ILIKE; a
-- trigram index keeps that off a sequential scan as the catalogue grows.
-- pg_trgm was enabled in 001_init.sql.

create index if not exists products_title_en_trgm_idx
    on products using gin (title_en gin_trgm_ops);
