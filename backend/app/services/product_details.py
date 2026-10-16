"""Sourcing detail for the product page, fetched lazily and cached.

The first view of a 1688 product (or the first after DETAIL_TTL_DAYS) spends
one detail call — inside the same daily cap as ingestion — and stores the
result on the row. Every later view reads the stored copy. If the call is
skipped (cap reached, out of credits, provider down) the page still renders
with whatever detail is stored, or none.
"""
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from .. import config, repository
from ..providers import metering
from ..providers.aggregator1688 import Aggregator1688Provider
from ..providers.base import OutOfCredits
from ..schemas import PriceTier, Product, ProductDetails

log = logging.getLogger(__name__)


def _is_fresh(fetched_at: datetime | None) -> bool:
    if fetched_at is None:
        return False
    return datetime.now(timezone.utc) - fetched_at < timedelta(days=config.DETAIL_TTL_DAYS)


def shipping_estimate(weight_kg: float | None) -> float | None:
    if not weight_kg:
        return None
    return round(config.SHIPPING_USD_BASE + weight_kg * config.SHIPPING_USD_PER_KG, 2)


def to_model(details: dict[str, Any], fetched_at: datetime | None) -> ProductDetails:
    rate = config.CNY_PER_USD
    tiers = [
        PriceTier(min_qty=t["min_qty"], price_cny=t["price_cny"],
                  price_usd=round(t["price_cny"] / rate, 2))
        for t in details.get("price_tiers") or []
    ]
    fields = {k: v for k, v in details.items() if k in ProductDetails.model_fields}
    fields.update(
        price_tiers=tiers,
        fetched_at=fetched_at,
        cny_per_usd=rate,
        shipping_estimate_usd=shipping_estimate(details.get("weight_kg")),
    )
    return ProductDetails(**fields)


async def _fetch(product_id: str, offer_id: str) -> dict[str, Any] | None:
    provider = Aggregator1688Provider()
    await metering.apply_budget(provider)
    try:
        body = await provider.fetch_detail(offer_id)
    except OutOfCredits as exc:
        log.warning("product page detail skipped: %s", exc)
        body = None
    finally:
        await metering.record_usage(provider)

    details = provider.parse_detail_info(body) if body else None
    if not details:
        return None

    tiers = details.get("price_tiers") or []
    cost_usd = round(tiers[0]["price_cny"] / config.CNY_PER_USD, 2) if tiers else None
    await repository.save_details(product_id, details, cost_usd)
    return details


async def attach_details(product: Product) -> Product:
    """Return `product` with `details` filled in where we have or can get them."""
    if product.source != "1688":
        return product

    row = await repository.product_details(product.id)
    if row is None:
        return product

    stored = row["details"]
    if isinstance(stored, str):  # asyncpg returns jsonb as text by default
        stored = json.loads(stored)
    fetched_at = row["details_fetched_at"]

    can_fetch = (
        config.AGG1688_DETAIL_ON_VIEW
        and config.AGG1688_DETAIL_URL
        and config.AGG1688_DETAIL_TOKEN
        and row["external_id"]
    )
    if not _is_fresh(fetched_at) and can_fetch:
        try:
            fresh = await _fetch(product.id, row["external_id"])
        except Exception:
            # The page must render even when the provider misbehaves.
            log.exception("product page detail fetch failed for %s", product.id)
            fresh = None
        if fresh:
            stored, fetched_at = fresh, datetime.now(timezone.utc)
            refreshed = await repository.get_product(product.id)
            if refreshed is not None:
                product = refreshed  # picks up the MOQ-tier cost

    if stored:
        product.details = to_model(stored, fetched_at)
    return product
