"""TikTok Shop via the jhzyapi aggregator.

The most valuable source for this product: TikTok is where products break
out, so `sold_count` and its change over time feed demand and trend — 55% of
the overall score. It is also the only source here that reports a **real USD
retail price**, rather than the derived one we have to use for 1688 wholesale.

Three endpoints are used; a fourth is deliberately not:
  * search        — discovery. One call returns ~30 products.
  * store/products— same payload shape as search, scoped to one seller.
  * product/detail— per-product enrichment (true sold_count, sale vs origin
    price, review score). One call per product, so it is capped.
  * product/reviews — NOT USED. It returns {"code":"error","msg":"调用失败"}
    for every parameter combination tried, and reviews are already embedded
    in the detail response under `review_info`, so it buys nothing.

Every response carries `charged_yuan` and `balance_yuan`; both are logged so
spend is visible rather than discovered when the balance hits zero.
"""
import logging
from typing import Any

import httpx

from .. import config
from .base import RawProduct

log = logging.getLogger(__name__)


def _walk(obj: Any, *keys: str) -> Any:
    for key in keys:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
    return obj


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


class TikTokShopProvider:
    name = "tiktok"
    source = "tiktok"

    def __init__(
        self,
        base_url: str = "",
        token: str = "",
        keywords: list[str] | None = None,
        seller_ids: list[str] | None = None,
    ) -> None:
        self.base_url = (base_url or config.TIKTOK_API_BASE).rstrip("/")
        self.token = token or config.TIKTOK_TOKEN
        self.keywords = keywords if keywords is not None else config.tiktok_keywords()
        self.seller_ids = (
            seller_ids if seller_ids is not None else config.tiktok_seller_ids()
        )

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.token and (self.keywords or self.seller_ids))

    def _log_spend(self, body: dict[str, Any], label: str) -> None:
        charged, balance = body.get("charged_yuan"), body.get("balance_yuan")
        if charged is not None or balance is not None:
            log.info(
                "tiktok: %s charged ¥%s, balance ¥%s", label, charged, balance
            )

    async def _get(self, client: httpx.AsyncClient, path: str, **params) -> dict[str, Any]:
        """GET with one retry.

        The aggregator intermittently answers a perfectly valid request with
        {"code":"error","msg":"调用失败"} and succeeds on an immediate repeat,
        so a single retry materially improves yield. A failed call still costs
        nothing, since only successful ones report charged_yuan.
        """
        body: dict[str, Any] = {}
        for attempt in (1, 2):
            response = await client.get(
                f"{self.base_url}/{path}",
                params={"token": self.token, "v": "1.0", **params},
            )
            response.raise_for_status()
            body = response.json()
            if body.get("code") == "success":
                return body
            if attempt == 1:
                log.info("tiktok: %s returned '%s', retrying once", path, body.get("msg"))
        return body

    # ── fetch ───────────────────────────────────────────────────────────────
    async def fetch(self, limit: int = 50) -> list[RawProduct]:
        if not self.configured:
            log.warning("tiktok: not configured, skipping")
            return []

        products: list[RawProduct] = []
        sources = [("search", k) for k in self.keywords] + [
            ("store", s) for s in self.seller_ids
        ]
        per_source = max(1, limit // max(1, len(sources)))

        async with httpx.AsyncClient(timeout=config.TIKTOK_TIMEOUT) as client:
            for kind, value in sources:
                try:
                    if kind == "search":
                        body = await self._get(client, "search", keyword=value, cursor=0)
                    else:
                        body = await self._get(
                            client, "store/products", seller_id=value, cursor=0
                        )
                except Exception as exc:
                    log.warning("tiktok: %s '%s' failed: %s", kind, value, exc)
                    continue

                self._log_spend(body, f"{kind} '{value}'")
                found = self.parse_products(body)
                log.info("tiktok: %s '%s' -> %d products", kind, value, len(found))
                products.extend(found[:per_source])

            if config.TIKTOK_ENRICH_TOP > 0:
                await self._enrich(client, products[: config.TIKTOK_ENRICH_TOP])

        return products

    def parse_products(self, body: dict[str, Any]) -> list[RawProduct]:
        """Search and store/products return the same product shape."""
        if body.get("code") != "success":
            log.error("tiktok error: %s", body.get("msg") or body.get("code"))
            return []

        items = _walk(body, "data", "products") or []
        products: list[RawProduct] = []

        for item in items:
            if not isinstance(item, dict):
                continue
            product_id = item.get("product_id")
            title = (item.get("title") or "").strip()
            if not product_id or not title:
                continue

            # Only trust the price when it is actually quoted in USD; a
            # localised storefront would otherwise be read as dollars.
            currency = _walk(item, "price", "currency")
            price = _as_float(_walk(item, "price", "current"))
            if price is not None and currency and currency != "USD":
                log.debug("tiktok: %s priced in %s, dropping price", product_id, currency)
                price = None

            products.append(
                RawProduct(
                    external_id=str(product_id),
                    title=title,
                    product_url=f"https://shop.tiktok.com/view/product/{product_id}",
                    source=self.source,
                    image_url=_walk(item, "image", "url"),
                    # This retail price is observed, not derived like 1688's.
                    price_usd=price,
                    cost_usd=None,          # TikTok never exposes supplier cost
                    orders_count=_as_int(item.get("sold_count")),
                    rating=_as_float(_walk(item, "rating", "score")),
                )
            )
        return products

    # ── detail enrichment ───────────────────────────────────────────────────
    async def _enrich(self, client: httpx.AsyncClient, products: list[RawProduct]) -> None:
        for product in products:
            try:
                body = await self._get(
                    client, "product/detail",
                    product_id=product.external_id, slug="product",
                    include_split_data="false",
                )
                self._log_spend(body, f"detail {product.external_id}")
                self.apply_detail(product, body)
            except Exception as exc:
                log.warning("tiktok: detail %s failed: %s", product.external_id, exc)

    def apply_detail(self, product: RawProduct, body: dict[str, Any]) -> RawProduct:
        """Overlay the detail call's better numbers onto a listing result."""
        if body.get("code") != "success":
            return product

        info = _walk(body, "data", "product_info")
        if not isinstance(info, dict):
            return product

        model = info.get("product_model") or {}

        sold = _as_int(model.get("sold_count"))
        if sold is not None and sold > (product.orders_count or 0):
            product.orders_count = sold

        name = model.get("name")
        if isinstance(name, str) and name.strip():
            product.title = name.strip()

        # The live sale price beats the listing price — it is what a buyer
        # actually pays today, discount included.
        min_price = _walk(info, "promotion_model", "promotion_product_price", "min_price")
        if isinstance(min_price, dict) and min_price.get("currency_name") == "USD":
            sale = _as_float(min_price.get("sale_price_decimal"))
            if sale:
                product.price_usd = sale

        score = _as_float(_walk(info, "review_model", "product_overall_score"))
        if score:
            product.rating = score

        return product
