"""Apify actor runner.

Fills the gaps AliExpress' affiliate catalogue doesn't cover (Amazon, TikTok,
Facebook Ad Library) without writing or maintaining scrapers. One actor per
source; the field mapping below is intentionally permissive because actor
output shapes vary between authors.
"""
import logging
from typing import Any

import httpx

from .. import config
from .base import RawProduct

log = logging.getLogger(__name__)

BASE_URL = "https://api.apify.com/v2"


def _first(item: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if item.get(key) not in (None, ""):
            return item[key]
    return None


def _as_float(value: Any) -> float | None:
    if isinstance(value, str):
        value = value.replace("$", "").replace(",", "").strip()
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    if isinstance(value, str):
        value = value.replace(",", "").strip()
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


class ApifyProvider:
    """Runs one actor synchronously and reads its dataset."""

    def __init__(self, actor_id: str, source: str, token: str = "") -> None:
        self.actor_id = actor_id
        self.source = source
        self.name = f"apify:{source}"
        self.token = token or config.APIFY_TOKEN

    @property
    def configured(self) -> bool:
        return bool(self.token and self.actor_id)

    async def fetch(self, limit: int = 50) -> list[RawProduct]:
        if not self.configured:
            log.warning("%s: not configured, skipping", self.name)
            return []

        actor = self.actor_id.replace("/", "~")
        url = f"{BASE_URL}/acts/{actor}/run-sync-get-dataset-items"

        # Actors are billed per run and can be slow; keep the timeout generous
        # but bounded so a hung actor can't wedge the whole ingestion run.
        async with httpx.AsyncClient(timeout=config.APIFY_TIMEOUT_SECONDS) as client:
            response = await client.post(
                url,
                params={"token": self.token, "limit": limit},
                json={"maxItems": limit},
            )
            response.raise_for_status()
            items = response.json()

        if not isinstance(items, list):
            log.error("%s: unexpected dataset shape %r", self.name, type(items))
            return []

        return self.parse(items)

    def parse(self, items: list[dict[str, Any]]) -> list[RawProduct]:
        products: list[RawProduct] = []
        for item in items:
            if not isinstance(item, dict):
                continue

            external_id = _first(item, "id", "productId", "asin", "itemId", "url")
            title = _first(item, "title", "name", "productTitle")
            if not external_id or not title:
                continue

            products.append(
                RawProduct(
                    external_id=str(external_id),
                    title=str(title).strip(),
                    product_url=str(_first(item, "url", "link", "productUrl") or ""),
                    source=self.source,
                    image_url=_first(item, "image", "imageUrl", "thumbnail"),
                    category=_first(item, "category", "categoryName"),
                    price_usd=_as_float(_first(item, "price", "currentPrice", "salePrice")),
                    cost_usd=_as_float(_first(item, "cost", "wholesalePrice", "supplierPrice")),
                    orders_count=_as_int(_first(item, "orders", "sold", "soldCount", "reviewsCount")),
                    rating=_as_float(_first(item, "rating", "stars")),
                    ad_count=_as_int(_first(item, "adCount", "ads", "activeAds")),
                    ad_platform=self.source if _first(item, "adCount", "ads", "activeAds") else None,
                )
            )
        return products
