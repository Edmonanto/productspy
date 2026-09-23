"""AliExpress Affiliate / Dropshipping API.

Official, free once your Portals application is approved, and it carries the
field this product needs most: supplier cost, which is what margin scoring
runs on. Limitation: it only covers the affiliate catalogue, a subset of all
listings.

Requests go to the Alibaba open-platform "sync" gateway and are signed with
HMAC-SHA256 over the sorted parameter string.
"""
import hashlib
import hmac
import logging
import time
from typing import Any

import httpx

from .. import config
from .base import RawProduct

log = logging.getLogger(__name__)

GATEWAY = "https://api-sg.aliexpress.com/sync"
HOT_PRODUCTS = "aliexpress.affiliate.hotproduct.query"


def _sign(params: dict[str, str], secret: str) -> str:
    """HMAC-SHA256 over key+value pairs sorted by key, uppercase hex."""
    payload = "".join(f"{k}{params[k]}" for k in sorted(params))
    return hmac.new(
        secret.encode(), payload.encode(), hashlib.sha256
    ).hexdigest().upper()


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class AliExpressProvider:
    name = "aliexpress"

    def __init__(self, app_key: str = "", app_secret: str = "") -> None:
        self.app_key = app_key or config.ALIEXPRESS_APP_KEY
        self.app_secret = app_secret or config.ALIEXPRESS_APP_SECRET

    @property
    def configured(self) -> bool:
        return bool(self.app_key and self.app_secret)

    async def fetch(self, limit: int = 50) -> list[RawProduct]:
        if not self.configured:
            log.warning("aliexpress: credentials not set, skipping")
            return []

        params: dict[str, str] = {
            "app_key": self.app_key,
            "method": HOT_PRODUCTS,
            "sign_method": "sha256",
            "timestamp": str(int(time.time() * 1000)),
            "format": "json",
            "v": "2.0",
            "page_no": "1",
            "page_size": str(min(limit, 50)),
            "target_currency": "USD",
            "target_language": "EN",
            "tracking_id": config.ALIEXPRESS_TRACKING_ID,
        }
        if config.ALIEXPRESS_CATEGORY_IDS:
            params["category_ids"] = config.ALIEXPRESS_CATEGORY_IDS

        params["sign"] = _sign(params, self.app_secret)

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(GATEWAY, data=params)
            response.raise_for_status()
            body = response.json()

        return self.parse(body)

    # Split out so it can be tested without a network call.
    def parse(self, body: dict[str, Any]) -> list[RawProduct]:
        # The gateway nests results a few levels deep and returns errors with
        # a 200, so walk defensively rather than indexing.
        if "error_response" in body:
            log.error("aliexpress error: %s", body["error_response"])
            return []

        resp = (
            body.get("aliexpress_affiliate_hotproduct_query_response")
            or body.get("resp_result")
            or {}
        )
        result = resp.get("resp_result", resp).get("result", {})
        items = (result.get("products") or {}).get("product") or []

        products: list[RawProduct] = []
        for item in items:
            external_id = str(
                item.get("product_id") or item.get("productId") or ""
            ).strip()
            if not external_id:
                continue

            # Retail is the sale price shown to shoppers; cost is what the
            # dropshipper actually pays, which is the discounted/app price.
            price = _as_float(item.get("target_original_price")) or _as_float(
                item.get("original_price")
            )
            cost = _as_float(item.get("target_sale_price")) or _as_float(
                item.get("sale_price")
            )
            if price is None:
                price = cost

            products.append(
                RawProduct(
                    external_id=external_id,
                    title=(item.get("product_title") or "").strip(),
                    product_url=item.get("product_detail_url") or "",
                    source=self.name,
                    image_url=item.get("product_main_image_url"),
                    category=str(item.get("first_level_category_name") or "") or None,
                    price_usd=price,
                    cost_usd=cost,
                    orders_count=_as_int(item.get("lastest_volume")),
                    rating=_as_float(item.get("evaluate_rate", "").rstrip("%") or None)
                    if isinstance(item.get("evaluate_rate"), str)
                    else _as_float(item.get("evaluate_rate")),
                )
            )
        return products
