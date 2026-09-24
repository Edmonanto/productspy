"""1688 via a third-party HTTP aggregator.

Distinct from `alibaba1688.py`, which talks to the official Open Platform and
needs an approved developer account. This one calls a reseller that proxies
1688's internal mtop API, so it works with nothing but a token — which is the
only reason it exists.

Two endpoints, deliberately used at different rates:
  * keyword search — one call returns ~60 offers. This is the discovery call.
  * item detail    — one call per offer, and the source of tiered/MOQ pricing.
    Enrichment is therefore opt-in and capped, because quota is per call and
    detail-for-everything would burn it in a single run.

Both responses are mtop payloads: deeply nested, heavy with tracking fields,
and returning errors with HTTP 200. Every accessor here walks defensively.
"""
import logging
import re
from typing import Any

import httpx

from .. import config
from .base import RawProduct

log = logging.getLogger(__name__)

# "已售2200+件" / "全网7900+件" / "已售1.3万+件"
_CN_COUNT = re.compile(r"([\d.]+)\s*([万亿])?")
_CN_SCALE = {"万": 10_000, "亿": 100_000_000}
_HTML_TAG = re.compile(r"<[^>]+>")


def strip_html(text: str) -> str:
    """Search titles embed the matched keyword in <font> tags."""
    return _HTML_TAG.sub("", text or "").strip()


def parse_cn_count(text: Any) -> int | None:
    """'已售1.3万+件' -> 13000. Returns None when nothing numeric is present."""
    if not isinstance(text, str):
        return None
    match = _CN_COUNT.search(text)
    if not match:
        return None
    try:
        value = float(match.group(1))
    except ValueError:
        return None
    return int(value * _CN_SCALE.get(match.group(2) or "", 1))


def parse_price(value: Any) -> float | None:
    """Prices arrive as '28', '3.97', or a range '3.97-17.86'.

    A range is the wholesale tier spread; take the low end, which is the
    volume price a sourcer would actually pay.
    """
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    match = re.search(r"\d+(?:\.\d+)?", value)
    return float(match.group()) if match else None


def _walk(obj: Any, *keys: str) -> Any:
    for key in keys:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
    return obj


class Aggregator1688Provider:
    name = "1688-aggregator"
    source = "1688"

    def __init__(
        self,
        search_url: str = "",
        search_token: str = "",
        detail_url: str = "",
        detail_token: str = "",
        keywords: list[str] | None = None,
    ) -> None:
        self.search_url = (search_url or config.AGG1688_SEARCH_URL).rstrip("/")
        self.search_token = search_token or config.AGG1688_SEARCH_TOKEN
        self.detail_url = (detail_url or config.AGG1688_DETAIL_URL).rstrip("/")
        self.detail_token = detail_token or config.AGG1688_DETAIL_TOKEN
        self.keywords = (
            keywords if keywords is not None else config.agg1688_keywords()
        )

    @property
    def configured(self) -> bool:
        return bool(self.search_url and self.search_token and self.keywords)

    # ── search ──────────────────────────────────────────────────────────────
    async def fetch(self, limit: int = 50) -> list[RawProduct]:
        if not self.configured:
            log.warning("1688-aggregator: not configured, skipping")
            return []

        products: list[RawProduct] = []
        per_keyword = max(1, limit // max(1, len(self.keywords)))

        async with httpx.AsyncClient(timeout=config.AGG1688_TIMEOUT) as client:
            for keyword in self.keywords:
                try:
                    response = await client.get(
                        self.search_url,
                        params={"keyword": keyword, "token": self.search_token},
                    )
                    response.raise_for_status()
                    body = response.json()
                except Exception as exc:
                    log.warning("1688-aggregator: search '%s' failed: %s", keyword, exc)
                    continue

                found = self.parse_search(body)
                log.info(
                    "1688-aggregator: '%s' -> %d offers (quota left: %s)",
                    keyword, len(found), body.get("left_nums", "?"),
                )
                products.extend(found[:per_keyword])

            if config.AGG1688_ENRICH_TOP > 0 and self.detail_token:
                await self._enrich(client, products[: config.AGG1688_ENRICH_TOP])

        return products

    def parse_search(self, body: dict[str, Any]) -> list[RawProduct]:
        if body.get("code") not in (None, "success", 200, "200"):
            log.error("1688-aggregator search error: %s", body.get("msg") or body.get("code"))
            return []

        items = _walk(body, "data", "data", "OFFER", "items") or []
        products: list[RawProduct] = []

        for wrapper in items:
            item = wrapper.get("data") if isinstance(wrapper, dict) else None
            if not isinstance(item, dict):
                continue

            # P4P entries are paid placement, not organic demand. Including
            # them would let an advertiser buy their way up our rankings.
            is_ad = bool(item.get("isP4P")) or item.get("block") == "P4P"
            if is_ad and not config.AGG1688_INCLUDE_ADS:
                continue

            offer_id = item.get("offerId")
            title = strip_html(item.get("title", ""))
            if not offer_id or not title:
                continue

            cost_cny = parse_price(_walk(item, "priceInfo", "price"))
            cost_usd = round(cost_cny / config.CNY_PER_USD, 2) if cost_cny else None

            # bookedCount is a clean integer present on every result; the
            # Chinese "已售…" string is the fallback when it is missing.
            orders = item.get("bookedCount")
            if not isinstance(orders, int):
                orders = parse_cn_count(_walk(item, "afterPrice", "text"))

            products.append(
                RawProduct(
                    external_id=str(offer_id),
                    title=title,
                    # linkUrl on ads is a tracking redirect; build the canonical one.
                    product_url=f"https://detail.1688.com/offer/{offer_id}.html",
                    source=self.source,
                    image_url=item.get("offerPicUrl"),
                    category=item.get("province"),
                    price_usd=(
                        round(cost_usd * config.WHOLESALE_MARKUP, 2)
                        if cost_usd else None
                    ),
                    # Computed from cost, not published by 1688 — see
                    # scoring.margin_score.
                    price_is_derived=cost_usd is not None,
                    cost_usd=cost_usd,
                    orders_count=orders,
                )
            )
        return products

    # ── detail enrichment ───────────────────────────────────────────────────
    async def _enrich(self, client: httpx.AsyncClient, products: list[RawProduct]) -> None:
        for product in products:
            try:
                response = await client.get(
                    self.detail_url,
                    params={"itemId": product.external_id, "token": self.detail_token},
                )
                response.raise_for_status()
                self.apply_detail(product, response.json())
            except Exception as exc:
                log.warning(
                    "1688-aggregator: detail %s failed: %s", product.external_id, exc
                )

    def apply_detail(self, product: RawProduct, body: dict[str, Any]) -> RawProduct:
        """Overlay the detail call's better numbers onto a search result."""
        data = body.get("data")
        if not isinstance(data, dict):
            return product

        # currentPrices carries the real wholesale tiers: the lowest beginAmount
        # is the price at minimum order quantity.
        tiers = _walk(data, "price", "priceModel", "currentPrices")
        if isinstance(tiers, list) and tiers:
            cheapest = min(
                (t for t in tiers if isinstance(t, dict) and parse_price(t.get("price"))),
                key=lambda t: t.get("beginAmount", 0),
                default=None,
            )
            if cheapest:
                cny = parse_price(cheapest.get("price"))
                if cny:
                    product.cost_usd = round(cny / config.CNY_PER_USD, 2)
                    product.price_usd = round(
                        product.cost_usd * config.WHOLESALE_MARKUP, 2
                    )
                    product.price_is_derived = True

        sold = _walk(data, "item", "saledCount")
        if isinstance(sold, int) and sold > (product.orders_count or 0):
            product.orders_count = sold

        title = _walk(data, "item", "offerTitle")
        if isinstance(title, str) and title.strip():
            product.title = title.strip()

        image = _walk(data, "item", "defaultOfferImg")
        if isinstance(image, str) and image:
            product.image_url = image

        return product
