"""Persistence for the Daily Winners engine. Plain SQL, like app/repository.py.

Every query is a literal string so tests/test_sql_integrity.py can parse it
against PostgreSQL's grammar and check its columns against the migrations.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import date
from typing import Any

import asyncpg

from app import db

from .collectors.base import AdRecord
from .extract import ProductGuess
from .scoring import ScoreResult

SOURCE = "winners"


def _j(value: Any) -> str:
    return json.dumps(value, default=str, ensure_ascii=False)


# ── Run log ─────────────────────────────────────────────────────────────────
async def start_run(market: str) -> int:
    return int(await db.fetchval(
        "insert into winner_runs (market) values ($1) returning id", market))


async def finish_run(run_id: int, status: str, stats: dict, errors: list) -> None:
    await db.execute(
        "update winner_runs set finished_at = now(), status = $2, "
        "stats = $3::jsonb, errors = $4::jsonb where id = $1",
        run_id, status, _j(stats), _j(errors),
    )


async def latest_runs() -> list[asyncpg.Record]:
    return await db.fetch(
        "select distinct on (market) market, started_at, finished_at, status, stats, errors "
        "from winner_runs order by market, started_at desc"
    )


# ── Ads ─────────────────────────────────────────────────────────────────────
async def upsert_ad(a: AdRecord) -> None:
    await db.execute(
        """
        insert into ad_creatives (platform, external_id, market, advertiser_name,
            advertiser_id, ad_text, landing_url, landing_domain, media_url,
            thumbnail_url, ad_url, started_at, is_active, variant_count, reach,
            views, likes, comments, shares, ctr, budget_level, intent_comments,
            sampled_comments, raw, last_seen_at)
        values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15,
                $16, $17, $18, $19, $20, $21, $22, $23, $24::jsonb, now())
        on conflict (platform, external_id, market) do update set
            last_seen_at = now(),
            is_active = excluded.is_active,
            variant_count = greatest(ad_creatives.variant_count, excluded.variant_count),
            landing_url = coalesce(excluded.landing_url, ad_creatives.landing_url),
            landing_domain = coalesce(excluded.landing_domain, ad_creatives.landing_domain),
            thumbnail_url = coalesce(excluded.thumbnail_url, ad_creatives.thumbnail_url),
            reach = coalesce(excluded.reach, ad_creatives.reach),
            views = coalesce(excluded.views, ad_creatives.views),
            likes = coalesce(excluded.likes, ad_creatives.likes),
            comments = coalesce(excluded.comments, ad_creatives.comments),
            shares = coalesce(excluded.shares, ad_creatives.shares),
            ctr = coalesce(excluded.ctr, ad_creatives.ctr),
            budget_level = coalesce(excluded.budget_level, ad_creatives.budget_level),
            intent_comments = coalesce(excluded.intent_comments, ad_creatives.intent_comments),
            sampled_comments = coalesce(excluded.sampled_comments, ad_creatives.sampled_comments)
        """,
        a.platform, a.external_id, a.market, a.advertiser_name, a.advertiser_id,
        a.ad_text, a.landing_url, a.landing_domain, a.media_url, a.thumbnail_url,
        a.ad_url, a.started_at, a.is_active, a.variant_count or 1, a.reach,
        a.views, a.likes, a.comments, a.shares, a.ctr, a.budget_level,
        a.intent_comments, a.sampled_comments, _j(a.raw or {}),
    )


def row_to_ad(r: asyncpg.Record) -> AdRecord:
    raw = r["raw"]
    return AdRecord(
        platform=r["platform"], external_id=r["external_id"], market=r["market"],
        advertiser_name=r["advertiser_name"], advertiser_id=r["advertiser_id"],
        ad_text=r["ad_text"], landing_url=r["landing_url"], media_url=r["media_url"],
        thumbnail_url=r["thumbnail_url"], ad_url=r["ad_url"], started_at=r["started_at"],
        is_active=r["is_active"], variant_count=r["variant_count"] or 1, reach=r["reach"],
        views=r["views"], likes=r["likes"], comments=r["comments"], shares=r["shares"],
        ctr=float(r["ctr"]) if r["ctr"] is not None else None,
        budget_level=r["budget_level"], intent_comments=r["intent_comments"],
        sampled_comments=r["sampled_comments"],
        raw=json.loads(raw) if isinstance(raw, str) else (raw or {}),
    )


async def unlinked_ads(market: str, limit: int = 600) -> list[asyncpg.Record]:
    """Ads seen in the last 3 days that haven't been tied to a product yet."""
    return await db.fetch(
        """
        select id, platform, external_id, market, advertiser_name, advertiser_id,
               ad_text, landing_url, media_url, thumbnail_url, ad_url, started_at,
               is_active, variant_count, reach, views, likes, comments, shares, ctr,
               budget_level, intent_comments, sampled_comments, raw
          from ad_creatives
         where market = $1 and product_id is null and not_product = false
           and last_seen_at > now() - interval '3 days'
         order by last_seen_at desc
         limit $2
        """,
        market, limit,
    )


async def mark_not_product(ad_ids: list[str]) -> None:
    if ad_ids:
        await db.execute(
            "update ad_creatives set not_product = true where id = any($1::uuid[])", ad_ids)


async def link_ad(ad_id: str, product_id: str) -> None:
    await db.execute("update ad_creatives set product_id = $2 where id = $1", ad_id, product_id)


# ── Products ────────────────────────────────────────────────────────────────
async def existing_keys() -> list[str]:
    rows = await db.fetch("select external_id from products where source = $1", SOURCE)
    return [r["external_id"] for r in rows]


async def upsert_product(guess: ProductGuess, first_ad: AdRecord) -> str:
    attrs = dict(guess.attributes or {})
    if guess.est_cost_usd:
        attrs["est_cost_usd"] = guess.est_cost_usd
    # products.product_url is required; an ad link stands in until a store is seen.
    url = first_ad.landing_url or first_ad.ad_url or ""
    return str(await db.fetchval(
        """
        insert into products (title, image_url, product_url, category, source,
            external_id, provider, attributes, updated_at)
        values ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, now())
        on conflict (source, external_id) do update set
            image_url = coalesce(products.image_url, excluded.image_url),
            product_url = case when products.product_url = '' then excluded.product_url
                               else products.product_url end,
            category = coalesce(products.category, excluded.category),
            attributes = excluded.attributes || products.attributes,
            updated_at = now()
        returning id
        """,
        guess.name, first_ad.thumbnail_url, url, guess.category, SOURCE, guess.key,
        first_ad.platform, _j(attrs),
    ))


async def products_needing_price(market: str, limit: int = 40) -> list[asyncpg.Record]:
    """Winners products in this market whose price/cost was never looked up."""
    return await db.fetch(
        """
        select p.id, p.title, p.attributes,
               (select a.landing_url from ad_creatives a
                 where a.product_id = p.id and a.landing_url like 'http%'
                 order by (a.landing_url like '%/products/%') desc, a.last_seen_at desc
                 limit 1) as url
          from products p
         where p.source = 'winners'
           and (p.price_usd is null or p.cost_usd is null)
           and coalesce((p.attributes ->> 'price_checked')::boolean, false) = false
           and exists (select 1 from ad_creatives a where a.product_id = p.id and a.market = $1)
         order by p.first_seen_at desc
         limit $2
        """,
        market, limit,
    )


async def save_prices(product_id: str, price_usd: float | None, cost_usd: float | None,
                      cost_estimated: bool, image: str | None) -> None:
    await db.execute(
        """
        update products set
            price_usd = coalesce($2, price_usd),
            cost_usd = coalesce($3, cost_usd),
            cost_estimated = $4,
            image_url = coalesce(image_url, $5),
            attributes = attributes || '{"price_checked": true}'::jsonb,
            updated_at = now()
         where id = $1
        """,
        product_id, price_usd, cost_usd, cost_estimated, image,
    )


async def add_supplier(product_id: str, platform: str, url: str, cost_usd: float) -> None:
    await db.execute(
        "insert into suppliers (product_id, platform, supplier_name, supplier_url, "
        "unit_cost_usd) values ($1, $2, $3, $4, $5)",
        product_id, platform, platform.title(), url, cost_usd,
    )


async def record_ad_signal(product_id: str, platform: str, ad_count: int) -> None:
    """Mirror advertiser counts into ad_signals so product pages show them too."""
    await db.execute(
        """
        insert into ad_signals (product_id, platform, ad_count, last_seen_at)
        values ($1, $2, $3, now())
        on conflict (product_id, platform) do update set
            ad_count = excluded.ad_count, last_seen_at = now()
        """,
        product_id, platform, ad_count,
    )


# ── Scoring inputs / outputs ────────────────────────────────────────────────
async def market_products_with_ads(market: str, window_days: int = 60) -> dict[str, tuple[asyncpg.Record, list[AdRecord]]]:
    rows = await db.fetch(
        """
        select product_id, platform, external_id, market, advertiser_name, advertiser_id,
               ad_text, landing_url, media_url, thumbnail_url, ad_url, started_at,
               is_active, variant_count, reach, views, likes, comments, shares, ctr,
               budget_level, intent_comments, sampled_comments, raw
          from ad_creatives
         where market = $1 and product_id is not null
           and last_seen_at > now() - make_interval(days => $2)
        """,
        market, window_days,
    )
    ads: dict[str, list[AdRecord]] = defaultdict(list)
    for r in rows:
        ads[str(r["product_id"])].append(row_to_ad(r))
    if not ads:
        return {}
    prods = await db.fetch(
        "select id, title, price_usd, cost_usd, cost_estimated, attributes "
        "from products where id = any($1::uuid[])",
        list(ads),
    )
    return {str(p["id"]): (p, ads[str(p["id"])]) for p in prods}


async def reject_ads(market: str, product_id: str, ads: list[AdRecord]) -> None:
    """Take ads off a product they don't advertise; they are not re-used."""
    for a in ads:
        await db.execute(
            "update ad_creatives set product_id = null, not_product = true, "
            "raw = coalesce(raw, '{}'::jsonb) || jsonb_build_object('rejected_from', $4::text) "
            "where platform = $1 and external_id = $2 and market = $3",
            a.platform, a.external_id, market, product_id,
        )


async def mark_not_physical(product_id: str) -> None:
    await db.execute(
        "update products set attributes = coalesce(attributes, '{}'::jsonb) || "
        "'{\"physical\": false}'::jsonb, updated_at = now() where id = $1",
        product_id,
    )


async def mark_verified(product_id: str, ad_keys: list[str], image_url: str | None,
                        name: str | None) -> None:
    await db.execute(
        """
        update products set
            attributes = coalesce(attributes, '{}'::jsonb) || jsonb_build_object(
                'verified_ads',
                (select coalesce(jsonb_agg(k), '[]'::jsonb) from (
                    select distinct k from jsonb_array_elements_text(
                        coalesce(attributes -> 'verified_ads', '[]'::jsonb) || $2::jsonb) k
                    limit 300) x)),
            image_url = coalesce($3, image_url),
            title = coalesce($4, title),
            updated_at = now()
         where id = $1
        """,
        product_id, _j(ad_keys), image_url, name,
    )


async def last_picks(market: str, before: date) -> dict[str, date]:
    rows = await db.fetch(
        "select product_id, max(pick_date) as last from daily_winners "
        "where market = $1 and pick_date < $2 and tier <> 'watch' group by product_id",
        market, before,
    )
    return {str(r["product_id"]): r["last"] for r in rows}


async def paid_ads_history(market: str, product_ids: list[str], before: date,
                           days: int = 21) -> dict[str, list[int]]:
    """Active paid ads per product on earlier scans (oldest first) — the time series
    behind the trend status. Read from the signals stored with each daily score."""
    if not product_ids:
        return {}
    rows = await db.fetch(
        """
        select product_id, scored_on,
               coalesce((signals ->> 'meta_ads')::int, 0) + coalesce((signals ->> 'tiktok_ads')::int, 0) as paid
          from winner_scores
         where market = $1 and product_id = any($2::uuid[])
           and scored_on < $3 and scored_on >= $3 - $4::int
         order by scored_on
        """,
        market, product_ids, before, days,
    )
    out: dict[str, list[int]] = {}
    for r in rows:
        out.setdefault(str(r["product_id"]), []).append(int(r["paid"]))
    return out


async def save_score(product_id: str, market: str, day: date, res: ScoreResult) -> str:
    return str(await db.fetchval(
        """
        insert into winner_scores (product_id, market, scored_on, total, breakdown,
            penalties, reasons, signals, confidence, excluded)
        values ($1, $2, $3, $4, $5::jsonb, $6::jsonb, $7::jsonb, $8::jsonb, $9, $10)
        on conflict (product_id, market, scored_on) do update set
            total = excluded.total, breakdown = excluded.breakdown,
            penalties = excluded.penalties, reasons = excluded.reasons,
            signals = excluded.signals, confidence = excluded.confidence,
            excluded = excluded.excluded, created_at = now()
        returning id
        """,
        product_id, market, day, res.total, _j(res.breakdown), _j(res.penalties),
        _j(res.reasons), _j(res.signals), res.confidence, res.excluded,
    ))


async def save_winners(market: str, day: date,
                       picks: list[tuple[str, ScoreResult, str]], score_ids: dict[str, str]) -> None:
    async with db.pool().acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "delete from daily_winners where market = $1 and pick_date = $2", market, day)
            for rank, (pid, res, tier) in enumerate(picks, start=1):
                await conn.execute(
                    "insert into daily_winners (market, pick_date, rank, tier, product_id, "
                    "score_id, total) values ($1, $2, $3, $4, $5, $6, $7)",
                    market, day, rank, tier, pid, score_ids.get(pid), res.total,
                )


# ── Reads for the API ───────────────────────────────────────────────────────
async def latest_pick_date(market: str, on_or_before: date) -> date | None:
    return await db.fetchval(
        "select max(pick_date) from daily_winners where market = $1 and pick_date <= $2",
        market, on_or_before,
    )


async def picks(market: str, day: date) -> list[asyncpg.Record]:
    return await db.fetch(
        """
        select dw.rank, dw.tier, dw.total, dw.product_id, dw.pick_date,
               ws.breakdown, ws.reasons, ws.penalties, ws.confidence, ws.signals,
               p.title, p.image_url, p.category, p.price_usd, p.cost_usd,
               p.cost_estimated, p.product_url, p.attributes,
               (select s.supplier_url from suppliers s where s.product_id = p.id
                 order by s.unit_cost_usd limit 1) as supplier_url,
               (select a.ad_url from ad_creatives a
                 where a.product_id = p.id and a.market = dw.market
                 order by (a.platform = 'meta') desc, a.variant_count desc, a.last_seen_at desc
                 limit 1) as ad_url,
               (select a.landing_url from ad_creatives a
                 where a.product_id = p.id and a.market = dw.market and a.landing_url like 'http%'
                 order by a.variant_count desc, a.last_seen_at desc
                 limit 1) as store_url
          from daily_winners dw
          join products p on p.id = dw.product_id
          left join winner_scores ws on ws.id = dw.score_id
         where dw.market = $1 and dw.pick_date = $2
         order by dw.rank
        """,
        market, day,
    )


async def pick_dates(market: str, since: date) -> list[asyncpg.Record]:
    return await db.fetch(
        """
        select pick_date, count(*) filter (where tier = 'winner') as winners, count(*) as total
          from daily_winners
         where market = $1 and pick_date >= $2
         group by pick_date
         order by pick_date desc
        """,
        market, since,
    )


async def product(product_id: str) -> asyncpg.Record | None:
    return await db.fetchrow(
        "select id, title, image_url, category, price_usd, cost_usd, cost_estimated, "
        "product_url, attributes, first_seen_at from products where id = $1",
        product_id,
    )


async def score_history(product_id: str, market: str) -> list[asyncpg.Record]:
    return await db.fetch(
        "select scored_on, total, breakdown, reasons, penalties, confidence, signals, excluded "
        "from winner_scores where product_id = $1 and market = $2 "
        "order by scored_on desc limit 30",
        product_id, market,
    )


async def product_ads(product_id: str, market: str) -> list[asyncpg.Record]:
    return await db.fetch(
        """
        select platform, advertiser_name, ad_text, landing_url, landing_domain,
               thumbnail_url, ad_url, started_at, variant_count, reach, views,
               likes, comments, shares, ctr
          from ad_creatives
         where product_id = $1 and market = $2
         order by coalesce(views, 0) + coalesce(likes, 0) * 10 + variant_count * 1000 desc
        """,
        product_id, market,
    )


async def product_suppliers(product_id: str) -> list[asyncpg.Record]:
    return await db.fetch(
        "select platform, supplier_name, supplier_url, unit_cost_usd "
        "from suppliers where product_id = $1 order by unit_cost_usd limit 5",
        product_id,
    )


# ── User preferences ────────────────────────────────────────────────────────
async def followed_markets(user_id: str) -> list[str]:
    value = await db.fetchval("select markets from user_preferences where user_id = $1", user_id)
    return list(value or [])


async def save_followed_markets(user_id: str, markets: list[str]) -> None:
    await db.execute(
        """
        insert into user_preferences (user_id, markets, updated_at) values ($1, $2, now())
        on conflict (user_id) do update set markets = excluded.markets, updated_at = now()
        """,
        user_id, markets,
    )
