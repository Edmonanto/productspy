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
        p.price_usd, p.cost_usd, p.source,
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


async def search(q: str, min_score: int = 40, limit: int = 40) -> tuple[list[Product], int]:
    rows = await db.fetch(
        f"{_PRODUCT_SELECT} "
        f"where p.title ilike '%' || $1 || '%' "
        f"  and coalesce(s.overall_score, 0) >= $2 "
        f"order by s.overall_score desc nulls last limit $3",
        q,
        min_score,
        limit,
    )
    total = await db.fetchval(
        "select count(*) from products p "
        "left join product_scores s on s.product_id = p.id "
        "where p.title ilike '%' || $1 || '%' and coalesce(s.overall_score, 0) >= $2",
        q,
        min_score,
    )
    return [_to_product(r) for r in rows], int(total or 0)


async def get_product(product_id: str) -> Product | None:
    row = await db.fetchrow(f"{_PRODUCT_SELECT} where p.id = $1", product_id)
    return _to_product(row) if row else None


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
