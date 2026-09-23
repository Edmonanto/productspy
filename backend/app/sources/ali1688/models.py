"""Normalized 1688 records. Prices are CNY, exactly as 1688 reports them."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Seller:
    company_name: str
    login_id: str | None = None
    member_id: str | None = None
    shop_url: str | None = None
    location: str | None = None          # "广东 惠州市" / "江苏宿迁"
    years_on_platform: int | None = None  # TrustPass years (诚信通)
    is_super_factory: bool = False
    factory_inspected: bool = False


@dataclass(frozen=True)
class SearchOffer:
    """One card from a keyword search result page."""
    offer_id: str
    title: str
    image_url: str | None
    price_cny: float | None
    sales_count: int | None           # "全网7900+件" -> 7900
    repurchase_rate: float | None     # "12%" -> 0.12
    is_ad: bool                       # paid placement (P4P)
    tags: list[str]
    seller: Seller

    @property
    def product_url(self) -> str:
        return offer_url(self.offer_id)


@dataclass(frozen=True)
class SearchPage:
    keyword: str
    page: int
    total_found: int
    has_more: bool
    offers: list[SearchOffer]


@dataclass(frozen=True)
class PriceTier:
    min_quantity: int
    price_cny: float


@dataclass(frozen=True)
class OfferDetail:
    """The item detail endpoint, trimmed to what the product page uses."""
    offer_id: str
    title: str
    images: list[str]
    video_url: str | None
    price_min_cny: float | None
    price_max_cny: float | None
    price_tiers: list[PriceTier]
    min_order_quantity: int | None
    unit: str | None
    sales_count: int | None
    category_id: str | None
    attributes: dict[str, str]
    sku_names: list[str]
    ships_from: str | None
    ship_within_days: int | None
    free_shipping: bool
    description_url: str | None
    seller: Seller
    services: list[str] = field(default_factory=list)

    @property
    def product_url(self) -> str:
        return offer_url(self.offer_id)


def offer_url(offer_id: str) -> str:
    # Canonical detail URL. Search results carry ad-tracking links instead;
    # we never store those.
    return f"https://detail.1688.com/offer/{offer_id}.html"
