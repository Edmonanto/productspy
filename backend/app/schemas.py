"""Response models.

These mirror the TypeScript interfaces in src/lib/api.ts exactly — field
names and nullability included. Changing one side requires changing the other.
Daily Winners responses are plain dicts built in app/routers/winners.py.
"""
from datetime import datetime

from pydantic import BaseModel


class WatchedProduct(BaseModel):
    id: str
    title: str
    image_url: str | None
    price_usd: float | None
    cost_usd: float | None
    # Best Daily Winners score in the last 7 days, and the market it was in.
    score: int | None
    market: str | None


class WatchlistItem(BaseModel):
    id: str
    product: WatchedProduct
    added_at: datetime


class WatchlistResponse(BaseModel):
    items: list[WatchlistItem]


class Subscription(BaseModel):
    plan: str
    status: str
    current_period_end: datetime | None


class Trial(BaseModel):
    active: bool
    plan: str
    ends_at: str | None
    days_left: int
    hours_left: int
    used: bool
    expired: bool
    eligible: bool
    length_days: int


class Me(BaseModel):
    id: str
    email: str
    name: str
    avatar_url: str | None
    subscription: Subscription
    trial: Trial | None = None


class BillingStatus(BaseModel):
    plan: str
    status: str
    provider: str
    current_period_end: datetime | None
    can_manage: bool
    trial: Trial | None = None
