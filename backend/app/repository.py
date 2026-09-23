"""Data access. Plain SQL against Postgres — no ORM."""
from typing import Any

import asyncpg

from . import config, db
from .schemas import AdSignal, Product, Score, Subscription, Supplier

# Products are always read with their score, suppliers and ad signals attached,
# so the frontend's Product shape can be built in a single round trip.
_PRODUCT_SELECT = """
    select
        p.id, p.title, p.image_url, p.product_url, p.category,
        p.price_usd, p.cost_usd, p.source, p.external_id, p.images, p.sales_count,
        s.overall_score, s.demand_score, s.margin_score,
        s.competition_score, s.trend_score, s.ai_summary,
        coalesce(sup.items, '[]'::json) as suppliers,
        coalesce(ads.items, '[]'::json) as ad_signals
    from products p
    left join product_scores s on s.product_id = p.id
    left join lateral (
        select json_agg(json_build_object(
            'platform', x.platform, 'supplier_name', x.supplier_name,
            'supplier_url', x.supplier_url, 'unit_cost_usd', x.unit_cost_usd,
            'shipping_days', x.shipping_days, 'rating', x.rating
        )) as items
        from suppliers x where x.product_id = p.id
    ) sup on true
    left join lateral (
        select json_agg(json_build_object(
            'platform', x.platform, 'ad_count', x.ad_count,
            'last_seen_at', x.last_seen_at
        )) as items
        from ad_signals x where x.product_id = p.id
    ) ads on true
"""


def _to_product(row: asyncpg.Record) -> Product:
    import json

    score = None
    if row["overall_score"] is not None:
        score = Score(
            overall_score=row["overall_score"],
            demand_score=row["demand_score"],
            margin_score=row["margin_score"],
            competition_score=row["competition_score"],
            trend_score=row["trend_score"],
            ai_summary=row["ai_summary"] or "",
        )

    suppliers = [Supplier(**s) for s in json.loads(row["suppliers"])]
    ad_signals = [AdSignal(**a) for a in json.loads(row["ad_signals"])]

    return Product(
        id=str(row["id"]),
        title=row["title"],
        image_url=row["image_url"],
        product_url=row["product_url"],
        category=row["category"],
        price_usd=float(row["price_usd"]) if row["price_usd"] is not None else None,
        cost_usd=float(row["cost_usd"]) if row["cost_usd"] is not None else None,
        source=row["source"],
        external_id=row["external_id"],
        images=list(row["images"] or []),
        sales_count=row["sales_count"],
        score=score,
        suppliers=suppliers,
        ad_signals=ad_signals,
    )


# ── Products ────────────────────────────────────────────────────────────────
async def trending(
    source: str = "", category: str = "", min_score: int = 0, limit: int = 40
) -> tuple[list[Product], int]:
    where: list[str] = ["coalesce(s.overall_score, 0) >= $1"]
    args: list[Any] = [min_score]

    if source and source != "all":
        args.append(source)
        where.append(f"p.source = ${len(args)}")
    if category and category != "all":
        args.append(category)
        where.append(f"p.category = ${len(args)}")

    clause = " and ".join(where)
    args.append(limit)

    rows = await db.fetch(
        f"{_PRODUCT_SELECT} where {clause} "
        f"order by s.overall_score desc nulls last, p.updated_at desc "
        f"limit ${len(args)}",
        *args,
    )
    total = await db.fetchval(
        f"select count(*) from products p "
        f"left join product_scores s on s.product_id = p.id where {clause}",
        *args[:-1],
    )
    return [_to_product(r) for r in rows], int(total or 0)


async def get_product(product_id: str) -> Product | None:
    row = await db.fetchrow(f"{_PRODUCT_SELECT} where p.id = $1::uuid", product_id)
    return _to_product(row) if row else None


async def get_product_by_external(source: str, external_id: str) -> Product | None:
    row = await db.fetchrow(
        f"{_PRODUCT_SELECT} where p.source = $1 and p.external_id = $2", source, external_id
    )
    return _to_product(row) if row else None


async def products_by_external_ids(source: str, external_ids: list[str]) -> list[Product]:
    """Products for these ids, in the given order (search result ranking)."""
    if not external_ids:
        return []
    rows = await db.fetch(
        f"{_PRODUCT_SELECT} where p.source = $1 and p.external_id = any($2::text[])",
        source,
        external_ids,
    )
    by_id = {r["external_id"]: _to_product(r) for r in rows}
    return [by_id[e] for e in external_ids if e in by_id]


# ── 1688 ingest ─────────────────────────────────────────────────────────────
async def upsert_product(
    *,
    source: str,
    external_id: str,
    title: str,
    image_url: str | None,
    product_url: str,
    category: str | None,
    price_cny: float | None,
    cost_usd: float | None,
    price_usd: float | None,
    sales_count: int | None,
    repurchase_rate: float | None,
    is_ad: bool | None,
    details: dict[str, Any],
) -> str:
    """Insert or refresh a product; returns its id.

    A re-seen product keeps its category if this sighting has none (a user's
    free-text search should not wipe the worker's category), and `details` is
    merged so search-level fields never erase detail-level ones.
    """
    import json

    product_id = await db.fetchval(
        """
        insert into products (source, external_id, title, image_url, product_url,
            category, price_cny, cost_usd, price_usd, sales_count, repurchase_rate,
            is_ad, details, updated_at)
        values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11,
                coalesce($12::boolean, false), $13::jsonb, now())
        on conflict (source, external_id) do update set
            title           = excluded.title,
            image_url       = coalesce(excluded.image_url, products.image_url),
            product_url     = excluded.product_url,
            category        = coalesce(excluded.category, products.category),
            price_cny       = coalesce(excluded.price_cny, products.price_cny),
            cost_usd        = coalesce(excluded.cost_usd, products.cost_usd),
            price_usd       = coalesce(excluded.price_usd, products.price_usd),
            sales_count     = coalesce(excluded.sales_count, products.sales_count),
            repurchase_rate = coalesce(excluded.repurchase_rate, products.repurchase_rate),
            is_ad           = coalesce($12::boolean, products.is_ad),
            details         = products.details || excluded.details,
            updated_at      = now()
        returning id
        """,
        source, external_id, title, image_url, product_url, category, price_cny,
        cost_usd, price_usd, sales_count, repurchase_rate, is_ad, json.dumps(details),
    )
    return str(product_id)


async def apply_detail(
    product_id: str, *, images: list[str], details: dict[str, Any]
) -> None:
    import json

    await db.execute(
        """
        update products set
            images = $2::text[],
            details = details || $3::jsonb,
            detail_fetched_at = now(),
            updated_at = now()
        where id = $1::uuid
        """,
        product_id, images, json.dumps(details),
    )


async def detail_fetched_at(product_id: str) -> Any:
    return await db.fetchval(
        "select detail_fetched_at from products where id = $1::uuid", product_id
    )


async def upsert_supplier(
    product_id: str,
    *,
    platform: str,
    supplier_name: str,
    supplier_url: str,
    unit_cost_usd: float,
    shipping_days: int,
    rating: float,
) -> None:
    await db.execute(
        """
        insert into suppliers (product_id, platform, supplier_name, supplier_url,
            unit_cost_usd, shipping_days, rating)
        values ($1::uuid, $2, $3, $4, $5, $6, $7)
        on conflict (product_id, platform) do update set
            supplier_name = excluded.supplier_name,
            supplier_url  = excluded.supplier_url,
            unit_cost_usd = excluded.unit_cost_usd,
            shipping_days = case when excluded.shipping_days > 0
                                 then excluded.shipping_days else suppliers.shipping_days end,
            rating        = excluded.rating
        """,
        product_id, platform, supplier_name, supplier_url, unit_cost_usd, shipping_days, rating,
    )


async def record_snapshot(product_id: str, sales_count: int | None, price_cny: float | None) -> None:
    """One row per product per UTC day; the latest sighting that day wins."""
    await db.execute(
        """
        insert into product_snapshots (product_id, sales_count, price_cny)
        values ($1::uuid, $2, $3)
        on conflict (product_id, captured_on) do update set
            sales_count = coalesce(excluded.sales_count, product_snapshots.sales_count),
            price_cny   = coalesce(excluded.price_cny, product_snapshots.price_cny)
        """,
        product_id, sales_count, price_cny,
    )


async def scoring_inputs(product_id: str) -> asyncpg.Record | None:
    """Raw signals for scoring, plus the last 30 days of snapshots."""
    return await db.fetchrow(
        """
        select p.sales_count, p.repurchase_rate, p.cost_usd,
               p.details ->> 'location' as location,
               coalesce((
                   select json_agg(json_build_object('day', x.captured_on, 'sales', x.sales_count))
                   from product_snapshots x
                   where x.product_id = p.id
                     and x.captured_on >= (now() at time zone 'utc')::date - 30
               ), '[]'::json) as snapshots
        from products p where p.id = $1::uuid
        """,
        product_id,
    )


# ── Search cache ────────────────────────────────────────────────────────────
async def cached_search(keyword: str, page: int, max_age_hours: float) -> asyncpg.Record | None:
    return await db.fetchrow(
        """
        select total_found, has_more, offer_ids from search_cache
        where keyword = $1 and page = $2
          and fetched_at > now() - make_interval(secs => $3)
        """,
        keyword, page, max_age_hours * 3600,
    )


async def store_search(
    keyword: str, page: int, total_found: int, has_more: bool, offer_ids: list[str]
) -> None:
    await db.execute(
        """
        insert into search_cache (keyword, page, total_found, has_more, offer_ids, fetched_at)
        values ($1, $2, $3, $4, $5::text[], now())
        on conflict (keyword, page) do update set
            total_found = excluded.total_found,
            has_more    = excluded.has_more,
            offer_ids   = excluded.offer_ids,
            fetched_at  = now()
        """,
        keyword, page, total_found, has_more, offer_ids,
    )


async def save_score(product_id: str, score: Score) -> None:
    await db.execute(
        """
        insert into product_scores (product_id, overall_score, demand_score,
            margin_score, competition_score, trend_score, ai_summary, scored_at)
        values ($1, $2, $3, $4, $5, $6, $7, now())
        on conflict (product_id) do update set
            overall_score = excluded.overall_score,
            demand_score = excluded.demand_score,
            margin_score = excluded.margin_score,
            competition_score = excluded.competition_score,
            trend_score = excluded.trend_score,
            ai_summary = excluded.ai_summary,
            scored_at = now()
        """,
        product_id,
        score.overall_score,
        score.demand_score,
        score.margin_score,
        score.competition_score,
        score.trend_score,
        score.ai_summary,
    )


# ── Watchlist ───────────────────────────────────────────────────────────────
async def watchlist(user_id: str) -> list[tuple[str, Product, Any]]:
    rows = await db.fetch(
        f"select w.id as watch_id, w.added_at, sub.* from watchlists w "
        f"join lateral ({_PRODUCT_SELECT} where p.id = w.product_id) sub on true "
        f"where w.user_id = $1 order by w.added_at desc",
        user_id,
    )
    return [(str(r["watch_id"]), _to_product(r), r["added_at"]) for r in rows]


async def watchlist_count(user_id: str) -> int:
    return int(
        await db.fetchval("select count(*) from watchlists where user_id = $1", user_id) or 0
    )


async def watchlist_add(user_id: str, product_id: str) -> None:
    await db.execute(
        "insert into watchlists (user_id, product_id) values ($1, $2) "
        "on conflict (user_id, product_id) do nothing",
        user_id,
        product_id,
    )


async def watchlist_remove(user_id: str, product_id: str) -> None:
    await db.execute(
        "delete from watchlists where user_id = $1 and product_id = $2",
        user_id,
        product_id,
    )


# ── Subscription & quota ────────────────────────────────────────────────────
async def subscription(user_id: str) -> tuple[Subscription, str]:
    """Return the user's subscription and billing provider (defaults to free)."""
    row = await db.fetchrow(
        "select plan, status, provider, current_period_end "
        "from subscriptions where user_id = $1",
        user_id,
    )
    if row is None:
        return Subscription(plan=config.DEFAULT_PLAN, status="active", current_period_end=None), "none"
    return (
        Subscription(
            plan=row["plan"],
            status=row["status"],
            current_period_end=row["current_period_end"],
        ),
        row["provider"],
    )


async def searches_used_today(user_id: str) -> int:
    return int(
        await db.fetchval(
            "select used from search_usage "
            "where user_id = $1 and usage_day = (now() at time zone 'utc')::date",
            user_id,
        )
        or 0
    )


async def increment_search(user_id: str) -> int:
    return int(
        await db.fetchval(
            """
            insert into search_usage (user_id, usage_day, used)
            values ($1, (now() at time zone 'utc')::date, 1)
            on conflict (user_id, usage_day)
            do update set used = search_usage.used + 1
            returning used
            """,
            user_id,
        )
        or 1
    )
