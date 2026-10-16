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
from .base import ApiCall, OutOfCredits, RawProduct

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


# The aggregator's refusal when a token's prepaid calls are spent:
# {"code": "error", "msg": "token次数不足"} — sent with HTTP 200.
_OUT_OF_CREDITS = "次数不足"


def _error_message(body: Any) -> str | None:
    """The error text of an error envelope, or None for a normal response.

    Search signals errors with code="error"; detail with a `ret` that doesn't
    start with SUCCESS ("SUCCESS::调用成功" on success).
    """
    if not isinstance(body, dict):
        return "non-object response"
    if body.get("code") not in (None, "success", 200, "200"):
        return str(body.get("msg") or body.get("code"))
    ret = body.get("ret")
    if isinstance(ret, str) and ret and not ret.startswith("SUCCESS"):
        return ret
    if isinstance(ret, list) and ret and not str(ret[0]).startswith("SUCCESS"):
        return str(ret[0])
    return None


def _balance(body: Any) -> int | None:
    """Calls left on the token. Detail reports `left_num`; some search
    deployments report `left_nums`."""
    if not isinstance(body, dict):
        return None
    for key in ("left_num", "left_nums"):
        value = body.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None


def _short(exc: Exception) -> str:
    return f"{exc.__class__.__name__}: {exc}"[:200]


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
        # Calls this provider may still make today, per endpoint. The worker
        # lowers these from api_usage before fetch(); the defaults are the
        # daily caps, so a run with no usage history still respects them.
        self.remaining: dict[str, int] = dict(self.daily_budgets)
        self.call_log: list[ApiCall] = []
        self.out_of_credits: set[str] = set()

    @property
    def daily_budgets(self) -> dict[str, int]:
        return {
            "search": config.AGG1688_DAILY_SEARCH_CALLS,
            "detail": config.AGG1688_DAILY_DETAIL_CALLS,
        }

    @property
    def configured(self) -> bool:
        return bool(self.search_url and self.search_token and self.keywords)

    # ── metered calls ───────────────────────────────────────────────────────
    async def _call(
        self, client: httpx.AsyncClient, endpoint: str, url: str, params: dict[str, Any]
    ) -> dict[str, Any] | None:
        """One paid request. Returns the body, or None if it failed.

        Raises OutOfCredits when the token is spent, so the caller stops
        instead of paying for — or at least waiting on — more refusals.
        """
        if self.remaining.get(endpoint, 0) <= 0:
            log.warning("1688-aggregator: daily %s budget used up, skipping call", endpoint)
            return None
        self.remaining[endpoint] -= 1

        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            body = response.json()
        except Exception as exc:
            self.call_log.append(ApiCall(endpoint, ok=False, error=_short(exc)))
            log.warning("1688-aggregator: %s call failed: %s", endpoint, exc)
            return None

        balance = _balance(body)
        message = _error_message(body)
        if message and _OUT_OF_CREDITS in message:
            self.call_log.append(
                ApiCall(endpoint, ok=False, balance=0, error=message, out_of_credits=True)
            )
            self.out_of_credits.add(endpoint)
            raise OutOfCredits(f"1688 {endpoint} token is out of credits")

        self.call_log.append(ApiCall(endpoint, ok=message is None, balance=balance, error=message))
        return body

    # ── search ──────────────────────────────────────────────────────────────
    async def fetch(self, limit: int = 50) -> list[RawProduct]:
        """Every offer from one search call per keyword.

        `limit` is deliberately not split across keywords: a search call is
        the unit of cost and returns ~60 offers, so keeping 16 of them would
        pay full price for a quarter of the data. Keywords define the
        catalogue size instead.
        """
        if not self.configured:
            log.warning("1688-aggregator: not configured, skipping")
            return []

        products: list[RawProduct] = []
        async with httpx.AsyncClient(timeout=config.AGG1688_TIMEOUT) as client:
            try:
                for keyword in self.keywords:
                    body = await self._call(
                        client, "search", self.search_url,
                        {"keyword": keyword, "token": self.search_token},
                    )
                    if body is None:
                        continue
                    found = self.parse_search(body)
                    log.info("1688-aggregator: '%s' -> %d offers", keyword, len(found))
                    products.extend(found)
            except OutOfCredits as exc:
                # Keep what earlier keywords returned; just stop searching.
                log.error("1688-aggregator: %s", exc)

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
                    # Not a category: 1688 returns the supplier's province
                    # here. Storing 浙江/广东 as a product category made the
                    # dashboard's category filter match nothing at all.
                    category=None,
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
                body = await self._call(
                    client, "detail", self.detail_url,
                    {"itemId": product.external_id, "token": self.detail_token},
                )
            except OutOfCredits as exc:
                log.error("1688-aggregator: %s", exc)
                return
            if body is None:
                continue
            try:
                self.apply_detail(product, body)
            except Exception as exc:
                log.warning(
                    "1688-aggregator: detail %s unparseable: %s", product.external_id, exc
                )

    async def fetch_detail(self, offer_id: str) -> dict[str, Any] | None:
        """One detail call for the product page. None when skipped or failed.

        Raises OutOfCredits like any other metered call.
        """
        if not (self.detail_url and self.detail_token):
            return None
        async with httpx.AsyncClient(timeout=config.AGG1688_TIMEOUT) as client:
            return await self._call(
                client, "detail", self.detail_url,
                {"itemId": offer_id, "token": self.detail_token},
            )

    @staticmethod
    def parse_detail_info(body: dict[str, Any]) -> dict[str, Any] | None:
        """The detail payload, reduced to what a sourcing decision needs.

        Stored as products.details and served to the product page. Prices
        stay in CNY here; USD is applied at read time with the current rate.
        """
        data = body.get("data") if isinstance(body, dict) else None
        if not isinstance(data, dict):
            return None
        item = data.get("item") or {}
        delivery = data.get("delivery") or {}

        tiers = []
        for t in _walk(data, "price", "priceModel", "currentPrices") or []:
            if not isinstance(t, dict):
                continue
            cny = parse_price(t.get("price"))
            qty = t.get("beginAmount")
            if cny and isinstance(qty, (int, float)):
                tiers.append({"min_qty": int(qty), "price_cny": cny})
        tiers.sort(key=lambda t: t["min_qty"])

        # Per-SKU weights in kg; the heaviest variant is the safe shipping basis.
        weights = [
            w for w in (delivery.get("skuWeight") or {}).values()
            if isinstance(w, (int, float)) and w > 0
        ]
        unit_weight = delivery.get("unitWeight")
        if not weights and isinstance(unit_weight, (int, float)) and unit_weight > 0:
            weights = [unit_weight]

        sold = _walk(data, "title", "selledNumber")
        if not isinstance(sold, int):
            sold = item.get("saledCount") if isinstance(item.get("saledCount"), int) else None

        ship_days = delivery.get("deliveryLimit")
        return {
            "images": [
                u for u in (_walk(data, "mainPic", "offerImgList") or []) if isinstance(u, str)
            ],
            "video_url": _walk(data, "mainPic", "videoUrl") or None,
            "price_tiers": tiers,
            "moq": tiers[0]["min_qty"] if tiers else None,
            "unit": item.get("offerUnit") or _walk(data, "price", "unit"),
            "units_sold": sold,
            "weight_kg": max(weights) if weights else None,
            "ships_from": delivery.get("location"),
            "ships_within_days": ship_days if isinstance(ship_days, int) else None,
            # postFree is free *domestic* (within China) delivery, not to the buyer.
            "free_shipping_in_china": bool(delivery.get("postFree")),
            "seller_name": item.get("companyName") or item.get("sellerLoginId"),
            "seller_url": item.get("winportUrl"),
            "variants": [
                s["name"] for s in (_walk(data, "mainPic", "skuImages") or [])
                if isinstance(s, dict) and s.get("name")
            ],
            "attributes": {
                str(p["name"]): str(p["value"])
                for p in (_walk(data, "attribute", "propsList") or [])
                if isinstance(p, dict) and p.get("name") and p.get("value") is not None
            },
        }

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
