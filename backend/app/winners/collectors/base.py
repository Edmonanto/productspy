"""Shared types for all collectors."""
from __future__ import annotations

import logging
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse, parse_qs, unquote

from app import config
from app.winners.markets import Market

log = logging.getLogger("engine.collectors")

# Comments that signal someone wants to BUY (EN / FR / ES / DE / AR)
INTENT_PATTERNS = re.compile(
    r"(where (can|do) i (buy|get)|link\??$|link pls|link please|need (this|one|it)|how much|"
    r"price\??|i want (this|one)|take my money|ordered|just ordered|does it ship|"
    r"o[uù] (l'?acheter|acheter|commander)|c'?est combien|combien|le lien|je veux|"
    r"dónde lo compro|cuánto cuesta|wo kann ich|كم السعر|وين القى|رابط)",
    re.IGNORECASE,
)


def count_intent(comments: list[str]) -> int:
    return sum(1 for c in comments if c and INTENT_PATTERNS.search(c.strip()))


@dataclass
class AdRecord:
    """One ad (or organic video) normalised across platforms."""
    platform: str                      # meta | tiktok_ads | tiktok_organic
    external_id: str
    market: str
    advertiser_name: Optional[str] = None
    advertiser_id: Optional[str] = None
    ad_text: Optional[str] = None
    landing_url: Optional[str] = None
    media_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    ad_url: Optional[str] = None
    started_at: Optional[datetime] = None
    is_active: bool = True
    variant_count: int = 1
    reach: Optional[int] = None
    views: Optional[int] = None
    likes: Optional[int] = None
    comments: Optional[int] = None
    shares: Optional[int] = None
    ctr: Optional[float] = None
    budget_level: Optional[int] = None
    intent_comments: Optional[int] = None
    sampled_comments: Optional[int] = None
    raw: dict = field(default_factory=dict)

    @property
    def landing_domain(self) -> Optional[str]:
        return domain_of(self.landing_url)


class Collector(ABC):
    name: str = ""
    #: True if the collector needs paid credentials (Apify etc.)
    paid: bool = False

    @abstractmethod
    def enabled(self) -> bool:
        """Return False if required credentials / deps are missing."""

    @abstractmethod
    async def collect(self, market: Market, limit: int = 200) -> list[AdRecord]:
        ...

    def proxy_for(self, market: Market) -> Optional[str]:
        return os.getenv(market.proxy_env) or config.PROXY_URL or None


# ---------- small helpers used by several collectors ----------

def to_int(v) -> Optional[int]:
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v).strip().replace(",", "").replace(" ", "").lower()
    mult = 1
    if s.endswith("k"):
        mult, s = 1_000, s[:-1]
    elif s.endswith("m"):
        mult, s = 1_000_000, s[:-1]
    elif s.endswith("b"):
        mult, s = 1_000_000_000, s[:-1]
    s = s.rstrip("+")
    try:
        return int(float(s) * mult)
    except ValueError:
        return None


def to_dt(v) -> Optional[datetime]:
    """Parse unix seconds/ms, ISO strings or 'YYYY-MM-DD'."""
    if v in (None, "", 0):
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    if isinstance(v, (int, float)) or (isinstance(v, str) and v.isdigit()):
        n = float(v)
        if n > 1e12:
            n /= 1000
        return datetime.fromtimestamp(n, tz=timezone.utc)
    s = str(v).strip().replace("Z", "+00:00")
    for fmt in (None, "%Y-%m-%d", "%b %d, %Y", "%d %b %Y"):
        try:
            d = datetime.fromisoformat(s) if fmt is None else datetime.strptime(s, fmt)
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def unwrap_redirect(url: Optional[str]) -> Optional[str]:
    """Facebook wraps outbound links in l.facebook.com/l.php?u=..."""
    if not url:
        return url
    try:
        p = urlparse(url)
        if p.netloc.endswith("facebook.com") and p.path.startswith("/l.php"):
            u = parse_qs(p.query).get("u", [None])[0]
            return unquote(u) if u else url
    except Exception:
        pass
    return url


def domain_of(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    try:
        host = urlparse(url if "://" in url else f"https://{url}").netloc.lower()
        return host[4:] if host.startswith("www.") else host or None
    except Exception:
        return None
