"""Response models.

These mirror the TypeScript interfaces in src/lib/api.ts exactly — field
names and nullability included. Changing one side requires changing the other.
"""
from datetime import datetime

from pydantic import BaseModel


class Score(BaseModel):
    overall_score: int
    demand_score: int
    margin_score: int
    competition_score: int
    trend_score: int
    ai_summary: str


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


class Product(BaseModel):
    id: str
    title: str
    # English rendering of a non-English (1688) title; null until translated.
    title_en: str | None = None
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


class DataStatus(BaseModel):
    sources: list[SourceStatus]
    products: dict[str, int]       # catalogue size per source
    last_updated_at: datetime | None
    is_admin: bool


class BillingStatus(BaseModel):
    plan: str
    status: str
    provider: str
    current_period_end: datetime | None
    search_quota: int | str
    can_manage: bool
