"""1688 Open Platform (Alibaba's domestic wholesale marketplace).

Better cost data than AliExpress for a sourcing tool: 1688 lists real factory
and wholesale prices, which is exactly what margin scoring needs, and it
carries MOQ and tiered pricing that AliExpress retail listings don't expose.

Auth differs from AliExpress in three ways, so don't copy that client:
  * gateway is gw.open.1688.com with a "param2" path scheme,
  * the signature is HMAC-SHA1 (not SHA256), uppercase hex,
  * the signed string starts with the URL path, then the sorted params.

The namespace and API name are configurable because which call you may
invoke depends on the service package granted to your app — hardcoding one
guess is how you get a signature that verifies against nothing.
"""
import hashlib
import hmac
import logging
from typing import Any

import httpx

from .. import config
from .base import RawProduct

log = logging.getLogger(__name__)

GATEWAY = "https://gw.open.1688.com/openapi"


def _sign(url_path: str, params: dict[str, str], secret: str) -> str:
    """HMAC-SHA1 over url_path + sorted key/value pairs, uppercase hex."""
    payload = url_path + "".join(f"{k}{params[k]}" for k in sorted(params))
    return hmac.new(
        secret.encode(), payload.encode("utf-8"), hashlib.sha1
    ).hexdigest().upper()


def _as_float(value: Any) -> float | None:
    if isinstance(value, str):
        value = value.replace("¥", "").replace(",", "").strip()
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


def _first(item: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if item.get(key) not in (None, "", []):
            return item[key]
    return None


class Alibaba1688Provider:
    name = "1688"

    def __init__(
        self,
        app_key: str = "",
        app_secret: str = "",
        access_token: str = "",
        namespace: str = "",
        api_name: str = "",
    ) -> None:
        self.app_key = app_key or config.ALIBABA1688_APP_KEY
        self.app_secret = app_secret or config.ALIBABA1688_APP_SECRET
        self.access_token = access_token or config.ALIBABA1688_ACCESS_TOKEN
        self.namespace = namespace or config.ALIBABA1688_NAMESPACE
        self.api_name = api_name or config.ALIBABA1688_API_NAME

    @property
    def configured(self) -> bool:
        return bool(self.app_key and self.app_secret)

    def _url_path(self) -> str:
        # param2/{version}/{namespace}/{apiName}/{appKey}
        return f"param2/1/{self.namespace}/{self.api_name}/{self.app_key}"

    async def fetch(self, limit: int = 50) -> list[RawProduct]:
        if not self.configured:
            log.warning("1688: credentials not set, skipping")
            return []

        params: dict[str, str] = {
            "pageSize": str(min(limit, 50)),
            "pageNo": "1",
        }
        if config.ALIBABA1688_KEYWORDS:
            params["keywords"] = config.ALIBABA1688_KEYWORDS
        if config.ALIBABA1688_CATEGORY_ID:
            params["categoryId"] = config.ALIBABA1688_CATEGORY_ID
        # Most product APIs are token-scoped; a few public ones are not.
        if self.access_token:
            params["access_token"] = self.access_token

        url_path = self._url_path()
        params["_aop_signature"] = _sign(url_path, params, self.app_secret)

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(f"{GATEWAY}/{url_path}", data=params)
            response.raise_for_status()
            body = response.json()

        return self.parse(body)

    def parse(self, body: dict[str, Any]) -> list[RawProduct]:
        # The gateway returns errors with a 200, so check before walking.
        if body.get("errorCode") or body.get("error_code"):
            log.error(
                "1688 error %s: %s",
                body.get("errorCode") or body.get("error_code"),
                body.get("errorMessage") or body.get("error_message"),
            )
            return []

        result = body.get("result", body)
        if isinstance(result, dict):
            items = (
                _first(result, "offerList", "products", "result", "data") or []
            )
        else:
            items = result or []
        if isinstance(items, dict):
            items = _first(items, "offerList", "products", "data") or []

        products: list[RawProduct] = []
        for item in items:
            if not isinstance(item, dict):
                continue

            external_id = _first(item, "offerId", "productId", "id")
            title = _first(item, "subject", "title", "productTitle", "name")
            if not external_id or not title:
                continue

            # 1688 prices are wholesale in CNY — this is the cost side, which
            # is the whole reason to source from here rather than retail.
            cost_cny = _as_float(
                _first(item, "price", "consignPrice", "wholesalePrice")
            )
            price_range = item.get("priceRange") or item.get("priceRanges")
            if cost_cny is None and isinstance(price_range, list) and price_range:
                cost_cny = _as_float(
                    _first(price_range[0], "price", "value")
                    if isinstance(price_range[0], dict)
                    else price_range[0]
                )

            cost_usd = (
                round(cost_cny / config.CNY_PER_USD, 2) if cost_cny else None
            )
            # No retail price on a wholesale listing — derive an indicative
            # one so margin scoring has something to work with. Flagged in
            # the README as an assumption, not a real market price.
            price_usd = (
                round(cost_usd * config.WHOLESALE_MARKUP, 2) if cost_usd else None
            )

            image = _first(item, "imageUrl", "image", "mainImage", "picUrl")
            if isinstance(image, dict):
                image = _first(image, "url", "fullPathImageURI", "images")
            if isinstance(image, list) and image:
                image = image[0]

            products.append(
                RawProduct(
                    external_id=str(external_id),
                    title=str(title).strip(),
                    product_url=str(
                        _first(item, "detailUrl", "offerUrl", "url")
                        or f"https://detail.1688.com/offer/{external_id}.html"
                    ),
                    source=self.name,
                    image_url=str(image) if image else None,
                    category=_first(item, "categoryName", "category"),
                    price_usd=price_usd,
                    cost_usd=cost_usd,
                    orders_count=_as_int(
                        _first(item, "saleQuantity", "soldQuantity", "tradeQuantity")
                    ),
                    rating=_as_float(_first(item, "score", "sellerScore")),
                )
            )
        return products
