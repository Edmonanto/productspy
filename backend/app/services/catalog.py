"""The product catalog: 1688 -> Postgres -> API.

Every 1688 call is metered, so the flow is always cache first:

- search:  (keyword, page) cached for SEARCH_CACHE_TTL_HOURS; a miss calls
           1688 once and ingests all offers on the page
- detail:  fetched when a product page is opened and the stored detail is
           older than DETAIL_CACHE_TTL_HOURS (or missing)

Ingesting upserts the product and its 1688 supplier, records today's sales
snapshot (the trend input), and rescores.
"""
import asyncio
import json
import logging
import uuid
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone

from .. import config, repository, scoring
from ..schemas import AdSignal, Product, Score
from ..sources import ali1688
from ..sources.ali1688 import OfferDetail, SearchOffer

log = logging.getLogger(__name__)

SOURCE = ali1688.SOURCE

# Ingest runs this many offers at once; stays under the DB pool size (10).
_INGEST_CONCURRENCY = 8


def to_usd(cny: float | None) -> float | None:
    return None if cny is None else round(cny * config.CNY_TO_USD, 2)


def suggested_price(cost_usd: float | None) -> float | None:
    return None if cost_usd is None else round(cost_usd * config.RETAIL_MARKUP, 2)


# ── search ──────────────────────────────────────────────────────────────────
async def search(
    keyword: str, page: int = 1, category: str | None = None
) -> tuple[list[Product], int]:
    """Products for a 1688 keyword search page, and 1688's total hit count."""
    keyword = keyword.strip()
    cached = await repository.cached_search(keyword, page, config.SEARCH_CACHE_TTL_HOURS)
    if cached is not None:
        products = await repository.products_by_external_ids(SOURCE, list(cached["offer_ids"]))
        return products, int(cached["total_found"])

    result = await ali1688.search(keyword, page)
    await _ingest_many(result.offers, category)

    offer_ids = [o.offer_id for o in result.offers]
    await repository.store_search(keyword, page, result.total_found, result.has_more, offer_ids)
    return await repository.products_by_external_ids(SOURCE, offer_ids), result.total_found


async def _ingest_many(offers: list[SearchOffer], category: str | None) -> None:
    gate = asyncio.Semaphore(_INGEST_CONCURRENCY)

    async def one(offer: SearchOffer) -> None:
        async with gate:
            await ingest_offer(offer, category)

    await asyncio.gather(*(one(o) for o in offers))


async def ingest_offer(offer: SearchOffer, category: str | None = None) -> str:
    cost = to_usd(offer.price_cny)
    product_id = await repository.upsert_product(
        source=SOURCE,
        external_id=offer.offer_id,
        title=offer.title,
        image_url=offer.image_url,
        product_url=offer.product_url,
        category=category,
        price_cny=offer.price_cny,
        cost_usd=cost,
        price_usd=suggested_price(cost),
        sales_count=offer.sales_count,
        repurchase_rate=offer.repurchase_rate,
        is_ad=offer.is_ad,
        details={
            "location": offer.seller.location,
            "seller": asdict(offer.seller),
            "tags": offer.tags,
        },
    )
    await repository.upsert_supplier(
        product_id,
        platform=SOURCE,
        supplier_name=offer.seller.company_name,
        supplier_url=offer.seller.shop_url or offer.product_url,
        unit_cost_usd=cost or 0,
        shipping_days=0,  # search cards don't say; filled in from detail
        rating=0,         # 1688 exposes no seller rating in these payloads
    )
    await repository.record_snapshot(product_id, offer.sales_count, offer.price_cny)
    await rescore(product_id)
    return product_id


# ── detail ──────────────────────────────────────────────────────────────────
async def get_product(product_id_or_offer_id: str) -> Product | None:
    """Look up by our uuid, or by a raw 1688 offer id (imported on first sight).

    1688 products get their detail refreshed when stale. A failed refresh is
    logged and the stored copy is served — a product page should not break
    because the provider is down or out of credits.
    """
    key = product_id_or_offer_id.strip()

    if _is_uuid(key):
        product = await repository.get_product(key)
    elif key.isdigit():
        product = await repository.get_product_by_external(SOURCE, key)
        if product is None:
            try:
                return await import_offer(key)
            except ali1688.Ali1688Error as exc:
                log.warning("1688 import of offer %s failed: %s", key, exc)
                return None
    else:
        return None

    if product is None or product.source != SOURCE or not product.external_id:
        return product
    if not config.DETAIL_AUTO_FETCH or not await _detail_is_stale(product.id):
        return product

    try:
        await ingest_detail(await ali1688.fetch_detail(product.external_id))
    except ali1688.Ali1688Error as exc:
        log.warning("1688 detail refresh for %s failed: %s", product.external_id, exc)
        return product
    return await repository.get_product(product.id)


async def import_offer(offer_id: str) -> Product | None:
    detail = await ali1688.fetch_detail(offer_id)
    product_id = await ingest_detail(detail)
    return await repository.get_product(product_id)


async def ingest_detail(detail: OfferDetail) -> str:
    cost = to_usd(detail.price_min_cny)
    product_id = await repository.upsert_product(
        source=SOURCE,
        external_id=detail.offer_id,
        title=detail.title,
        image_url=detail.images[0] if detail.images else None,
        product_url=detail.product_url,
        category=None,
        price_cny=detail.price_min_cny,
        cost_usd=cost,
        price_usd=suggested_price(cost),
        sales_count=detail.sales_count,
        repurchase_rate=None,  # only search results carry these two;
        is_ad=None,            # None keeps the stored value
        details={
            "location": detail.ships_from,
            "seller": asdict(detail.seller),
        },
    )
    await repository.apply_detail(
        product_id,
        images=detail.images,
        details={
            "price_max_cny": detail.price_max_cny,
            "price_tiers": [asdict(t) for t in detail.price_tiers],
            "min_order_quantity": detail.min_order_quantity,
            "unit": detail.unit,
            "attributes": detail.attributes,
            "sku_names": detail.sku_names,
            "ships_from": detail.ships_from,
            "ship_within_days": detail.ship_within_days,
            "free_shipping": detail.free_shipping,
            "video_url": detail.video_url,
            "description_url": detail.description_url,
            "services": detail.services,
            "category_id": detail.category_id,
        },
    )
    await repository.upsert_supplier(
        product_id,
        platform=SOURCE,
        supplier_name=detail.seller.company_name,
        supplier_url=detail.seller.shop_url or detail.product_url,
        unit_cost_usd=cost or 0,
        shipping_days=detail.ship_within_days or 0,
        rating=0,
    )
    await repository.record_snapshot(product_id, detail.sales_count, detail.price_min_cny)
    await rescore(product_id)
    return product_id


async def _detail_is_stale(product_id: str) -> bool:
    fetched_at: datetime | None = await repository.detail_fetched_at(product_id)
    if fetched_at is None:
        return True
    age = datetime.now(timezone.utc) - fetched_at
    return age > timedelta(hours=config.DETAIL_CACHE_TTL_HOURS)


# ── scoring ─────────────────────────────────────────────────────────────────
async def rescore(product_id: str, ad_signals: list[AdSignal] | None = None) -> Score | None:
    row = await repository.scoring_inputs(product_id)
    if row is None:
        return None

    snapshots = [
        (date.fromisoformat(s["day"]), s["sales"])
        for s in json.loads(row["snapshots"])
        if s.get("sales") is not None
    ]
    score = scoring.score(
        scoring.Signals(
            sales_count=row["sales_count"],
            repurchase_rate=float(row["repurchase_rate"]) if row["repurchase_rate"] is not None else None,
            cost_usd=float(row["cost_usd"]) if row["cost_usd"] is not None else None,
            snapshots=snapshots,
            ad_signals=ad_signals or [],
            location=row["location"],
        )
    )
    await repository.save_score(product_id, score)
    return score


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False
