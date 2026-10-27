"""Response models.

These mirror the TypeScript interfaces in src/lib/api.ts exactly — field
names and nullability included. Changing one side requires changing the other.
Daily Winners responses are plain dicts built in app/routers/winners.py.
"""
from datetime import datetime

from typing import Literal

from pydantic import BaseModel, Field


class WatchedProduct(BaseModel):
    id: str
    title: str
    image_url: str | None
    price_usd: float | None
    cost_usd: float | None
    # Best Daily Winners score in the last 7 days, and the market it was in.
    score: int | None
    market: str | None
    category: str | None = None


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
    can_manage: bool
    trial: Trial | None = None
