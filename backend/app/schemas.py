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
    image_url: str | None
    product_url: str
    category: str | None
    price_usd: float | None
    cost_usd: float | None
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


class BillingStatus(BaseModel):
    plan: str
    status: str
    provider: str
    current_period_end: datetime | None
    search_quota: int | str
    can_manage: bool
