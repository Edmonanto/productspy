"""Response models.

These mirror the TypeScript interfaces in src/lib/api.ts exactly — field
names and nullability included. Changing one side requires changing the other.
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Score(BaseModel):
    overall_score: int
    demand_score: int
    margin_score: int
    competition_score: int
    trend_score: int
    ai_summary: str
    # False while there is no snapshot ~TREND_WINDOW_DAYS old: trend_score
    # is then the neutral default, not a measurement.
    trend_known: bool = False


class Supplier(BaseModel):
    platform: str
    supplier_name: str
    supplier_url: str
    unit_cost_usd: float
    shipping_days: int
    rating: float


class AdSignal(BaseModel):
    platform: str
    ad_count: int
    last_seen_at: datetime


class PriceTier(BaseModel):
    min_qty: int
    price_cny: float
    price_usd: float


class ProductDetails(BaseModel):
    """Sourcing detail from the 1688 detail endpoint (product page only)."""
    images: list[str] = []
    video_url: str | None = None
    price_tiers: list[PriceTier] = []
    moq: int | None = None
    unit: str | None = None
    units_sold: int | None = None
    weight_kg: float | None = None
    ships_from: str | None = None
    ships_within_days: int | None = None
    free_shipping_in_china: bool = False
    seller_name: str | None = None
    seller_url: str | None = None
    variants: list[str] = []
    attributes: dict[str, str] = {}
    fetched_at: datetime | None = None
    # Calculator inputs, so the frontend uses the backend's numbers.
    cny_per_usd: float
    shipping_estimate_usd: float | None = None  # from weight; an estimate


class Product(BaseModel):
    id: str
    title: str
    # English rendering of a non-English (1688) title; null until translated.
    title_en: str | None = None
    orders_count: int | None = None  # units sold, as last reported by the source
    image_url: str | None
    product_url: str
    category: str | None
    price_usd: float | None
    cost_usd: float | None
    price_is_derived: bool = False
    source: str
    score: Score | None
    suppliers: list[Supplier] = []
    ad_signals: list[AdSignal] = []
    # Only on GET /products/{id}; list endpoints leave it null.
    details: ProductDetails | None = None


class ProductList(BaseModel):
    products: list[Product]
    total: int


class RescoreResponse(BaseModel):
    score: Score


class WatchlistItem(BaseModel):
    id: str
    product: Product
    added_at: datetime


class WatchlistResponse(BaseModel):
    items: list[WatchlistItem]


class Subscription(BaseModel):
    plan: str
    status: str
    current_period_end: datetime | None


class Quota(BaseModel):
    plan: str
    limit: int | str
    used: int
    remaining: int | str


class Me(BaseModel):
    id: str
    email: str
    name: str
    avatar_url: str | None
    subscription: Subscription
    quota: Quota


class EndpointUsage(BaseModel):
    endpoint: str
    calls_today: int
    daily_cap: int | None
    balance: int | None          # calls left, as last reported by the provider
    out_of_credits: bool
    last_error: str | None


class SourceStatus(BaseModel):
    provider: str
    # ok | low_credits | out_of_credits | failing | never_run
    state: str
    last_run_at: datetime | None
    last_success_at: datetime | None
    # Operator detail — only populated for ADMIN_EMAILS.
    last_error: str | None = None
    endpoints: list[EndpointUsage] = []


class ScoreBucket(BaseModel):
    range: str                     # "0–19" ... "80–100"
    count: int


class DataStatus(BaseModel):
    sources: list[SourceStatus]
    products: dict[str, int]       # catalogue size per source
    score_distribution: list[ScoreBucket] = []
    last_updated_at: datetime | None
    is_admin: bool


class QuoteCreate(BaseModel):
    product_id: str
    quantity: int = Field(gt=0, le=1_000_000)
    destination_country: str = Field(min_length=2, max_length=56)
    target_price_usd: float | None = Field(default=None, gt=0, le=100_000)
    notes: str = Field(default="", max_length=2000)


class QuoteReply(BaseModel):
    status: Literal["quoted", "closed"] = "quoted"
    quoted_unit_usd: float | None = Field(default=None, ge=0, le=100_000)
    quoted_shipping_usd: float | None = Field(default=None, ge=0, le=100_000)
    reply: str = Field(default="", max_length=4000)


class Quote(BaseModel):
    id: str
    user_email: str                # shown to admins; it's the requester's own email otherwise
    product_id: str | None
    product_title: str
    quantity: int
    destination_country: str
    target_price_usd: float | None
    notes: str
    status: str                    # open | quoted | closed
    quoted_unit_usd: float | None
    quoted_shipping_usd: float | None
    reply: str
    created_at: datetime
    replied_at: datetime | None


class QuoteList(BaseModel):
    quotes: list[Quote]
    is_admin: bool


class BillingStatus(BaseModel):
    plan: str
    status: str
    provider: str
    current_period_end: datetime | None
    search_quota: int | str
    can_manage: bool
