"""Provider interface.

A provider fetches raw products from one source. Everything downstream
(normalising, upserting, snapshotting, scoring) is provider-agnostic, so
swapping AliExpress for Apify — or adding Keepa later — is a config change.
"""
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class RawProduct:
    """One product as returned by a source, before it touches the database."""

    external_id: str
    title: str
    product_url: str
    source: str                      # aliexpress | amazon | tiktok | ...
    image_url: str | None = None
    category: str | None = None
    price_usd: float | None = None   # retail price we'd sell at
    cost_usd: float | None = None    # supplier cost — drives margin_score
    orders_count: int | None = None  # units sold — drives demand_score
    rating: float | None = None
    ad_count: int | None = None      # advertisers seen — drives competition_score
    ad_platform: str | None = None


@runtime_checkable
class Provider(Protocol):
    name: str

    async def fetch(self, limit: int) -> list[RawProduct]:
        """Return up to `limit` products. Must not raise on empty results."""
        ...
