"""Raw 1688 JSON -> normalized models.

Pure functions, no I/O. The upstream payloads are the 1688 mobile/PC page
models and change without notice, so every lookup is defensive: a missing
field yields None/empty rather than an exception, and one malformed search
card is skipped instead of failing the whole page.
"""
import re
from typing import Any

from .models import OfferDetail, PriceTier, SearchOffer, SearchPage, Seller

_TAG_RE = re.compile(r"<[^>]+>")
_COUNT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(万)?")


# ── helpers ─────────────────────────────────────────────────────────────────
def _get(obj: Any, *path: str | int, default: Any = None) -> Any:
    for key in path:
        if isinstance(obj, dict) and isinstance(key, str):
            obj = obj.get(key)
        elif isinstance(obj, list) and isinstance(key, int) and -len(obj) <= key < len(obj):
            obj = obj[key]
        else:
            return default
        if obj is None:
            return default
    return obj


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def clean_title(title: str | None) -> str:
    """Search titles highlight the keyword with <font> tags."""
    return _TAG_RE.sub("", title or "").strip()


def parse_count(text: Any) -> int | None:
    """'全网7900+件' -> 7900, '已售1.2万+件' -> 12000, 71 -> 71."""
    if isinstance(text, (int, float)):
        return int(text)
    match = _COUNT_RE.search(str(text or ""))
    if not match:
        return None
    number = float(match.group(1))
    return int(number * 10_000) if match.group(2) else int(number)


def parse_percent(text: Any) -> float | None:
    """'12%' -> 0.12"""
    value = _float(str(text or "").strip().rstrip("%"))
    return None if value is None else value / 100


def parse_price_range(text: Any) -> tuple[float | None, float | None]:
    """'3.97-17.86' -> (3.97, 17.86), '28' -> (28.0, 28.0)"""
    parts = [_float(p) for p in str(text or "").split("-")]
    parts = [p for p in parts if p is not None]
    if not parts:
        return None, None
    return min(parts), max(parts)


# ── search ──────────────────────────────────────────────────────────────────
def parse_search(payload: dict[str, Any], keyword: str, page: int) -> SearchPage:
    offer_block = _get(payload, "data", "data", "OFFER", default={})
    offers: list[SearchOffer] = []
    for item in offer_block.get("items") or []:
        offer = _parse_search_item(_get(item, "data", default={}))
        if offer is not None:
            offers.append(offer)

    return SearchPage(
        keyword=keyword,
        page=page,
        total_found=_int(offer_block.get("found")) or 0,
        has_more=bool(offer_block.get("hasMore")),
        offers=offers,
    )


def _parse_search_item(d: dict[str, Any]) -> SearchOffer | None:
    offer_id = str(d.get("offerId") or "").strip()
    title = clean_title(d.get("title"))
    if not offer_id or not title:
        return None

    sales_text = _get(d, "afterPrice", "text") if _get(d, "afterPrice", "matKey") == "sale_count" else None
    location = " ".join(p for p in (d.get("province"), d.get("city")) if p) or None

    return SearchOffer(
        offer_id=offer_id,
        title=title,
        image_url=d.get("offerPicUrl") or _get(d, "list", "cover", "pic"),
        price_cny=_float(_get(d, "priceInfo", "price")),
        sales_count=parse_count(sales_text) if sales_text else _int(d.get("bookedCount")),
        repurchase_rate=parse_percent(d.get("offerRepurchaseRate")),
        is_ad=bool(d.get("isP4P") or d.get("block") == "P4P"),
        tags=[t for t in (_get(d, "offerTags", "promotionTags", default=[]) or []) if isinstance(t, str)],
        seller=Seller(
            company_name=_get(d, "shop", "text") or d.get("loginId") or "",
            login_id=d.get("loginId"),
            member_id=d.get("memberId"),
            shop_url=_get(d, "shopAddition", "shopLinkUrl") or d.get("winPortUrl"),
            location=location,
            years_on_platform=_int(_get(d, "shop", "tpYear")),
            is_super_factory=bool(d.get("superFactory")),
            factory_inspected=bool(d.get("factoryInspection")),
        ),
    )


# ── detail ──────────────────────────────────────────────────────────────────
def parse_detail(payload: dict[str, Any]) -> OfferDetail | None:
    d = payload.get("data") or {}
    item = d.get("item") or {}
    offer_id = str(item.get("offerId") or _get(d, "mainPic", "offerId") or "").strip()
    if not offer_id:
        return None

    price_model = _get(d, "price", "priceModel", default={})
    tiers = [
        PriceTier(min_quantity=_int(t.get("beginAmount")) or 1, price_cny=price)
        for t in price_model.get("currentPrices") or []
        if (price := _float(t.get("price"))) is not None
    ]
    price_min, price_max = parse_price_range(
        price_model.get("originalPriceDisplay") or _get(d, "mainPic", "offerInfoModel", "price")
    )
    if price_min is None and tiers:
        price_min = min(t.price_cny for t in tiers)
        price_max = max(t.price_cny for t in tiers)

    delivery = d.get("delivery") or {}
    return OfferDetail(
        offer_id=offer_id,
        title=clean_title(_get(d, "title", "title") or item.get("offerTitle")),
        images=list(_get(d, "mainPic", "offerImgList", default=[]) or []),
        video_url=_get(d, "mainPic", "videoUrl") or None,
        price_min_cny=price_min,
        price_max_cny=price_max,
        price_tiers=tiers,
        min_order_quantity=tiers[0].min_quantity if tiers else None,
        unit=item.get("offerUnit") or _get(d, "price", "unit"),
        sales_count=_int(_get(d, "title", "selledNumber")) or _int(item.get("saledCount")),
        category_id=str(item["postCategoryId"]) if item.get("postCategoryId") else None,
        attributes={
            str(p["name"]): str(p["value"])
            for p in _get(d, "attribute", "propsList", default=[]) or []
            if p.get("name") and p.get("value") is not None
        },
        sku_names=[s["name"] for s in _get(d, "mainPic", "skuImages", default=[]) or [] if s.get("name")],
        ships_from=delivery.get("location"),
        ship_within_days=_int(delivery.get("deliveryLimit")),
        free_shipping=bool(delivery.get("postFree")),
        description_url=_get(d, "description", "detailUrl"),
        services=[
            s["serviceName"] for s in _get(d, "service", "serviceDetail", default=[]) or [] if s.get("serviceName")
        ],
        seller=Seller(
            company_name=item.get("companyName") or item.get("sellerLoginId") or "",
            login_id=item.get("sellerLoginId"),
            member_id=item.get("sellerMemberId"),
            shop_url=item.get("winportUrl"),
            location=delivery.get("location"),
        ),
    )
