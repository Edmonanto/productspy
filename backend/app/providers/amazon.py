"""Amazon via the jhzyapi aggregator, across multiple marketplaces.

Amazon's role here is the **retail price anchor**. 1688 gives a real wholesale
cost but no retail price, so margin has to be derived from a markup guess;
Amazon supplies an observed retail price for the same class of product, which
is the number a real margin should be computed against.

What it does *not* give is units sold — Amazon publishes no sales count — so
`orders_count` is deliberately left None rather than substituting review
count, which is a popularity proxy and not the same thing. Demand keeps
coming from TikTok and 1688.

The hard part is locale. The API returns display strings, not numbers, and
they are formatted per marketplace:

    US  $501.60      4.5 out of 5 stars   (75,618)   (11.9K)
    UK  £8.99        4.6 out of 5 stars   (45.4K)
    DE  229,99€      4,6 von 5 Sternen    (36.976)

In DE a dot is a *thousands* separator, so a naive float() reads 36.976
reviews instead of 36,976 — a 1000x error — and reads the price 10,99 € as
either 1099 or nothing. Parsing is therefore site-aware.
"""
import logging
import re
from typing import Any

import httpx

from .. import config
from .base import RawProduct

log = logging.getLogger(__name__)

# Marketplaces where "," is the decimal separator and "." groups thousands.
COMMA_DECIMAL_SITES = {"DE", "FR", "IT", "ES", "NL", "SE", "PL", "BE", "TR", "BR"}

SITE_CURRENCY = {
    "US": "USD", "CA": "CAD", "UK": "GBP", "DE": "EUR", "FR": "EUR",
    "IT": "EUR", "ES": "EUR", "NL": "EUR", "BE": "EUR", "IE": "EUR",
    "JP": "JPY", "AU": "AUD", "IN": "INR", "MX": "MXN", "BR": "BRL",
}

SITE_TLD = {
    "US": "com", "UK": "co.uk", "DE": "de", "FR": "fr", "IT": "it",
    "ES": "es", "CA": "ca", "JP": "co.jp", "AU": "com.au", "IN": "in",
    "MX": "com.mx", "BR": "com.br", "NL": "nl", "SE": "se", "PL": "pl",
}

_SUFFIX = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}


def parse_number(text: Any, site: str) -> float | None:
    """Parse a localised display number.

    `site` decides which separator means what, which is the whole point:
    '36.976' is 36976 on amazon.de and 36.976 on amazon.com.
    """
    if not isinstance(text, str):
        return None

    cleaned = text.strip().strip("()").replace("\xa0", " ")
    # Drop currency symbols, letters and spaces, but keep a K/M/B multiplier.
    multiplier = 1
    match = re.search(r"([\d.,]+)\s*([KMB])\b", cleaned, re.I)
    if match:
        multiplier = _SUFFIX[match.group(2).upper()]
        number = match.group(1)
    else:
        found = re.search(r"[\d.,]+", cleaned)
        if not found:
            return None
        number = found.group()

    if site.upper() in COMMA_DECIMAL_SITES:
        number = number.replace(".", "").replace(",", ".")
    else:
        number = number.replace(",", "")

    # A trailing separator ("1.234." ) leaves a malformed float.
    number = number.rstrip(".")
    try:
        return float(number) * multiplier
    except ValueError:
        return None


def to_usd(amount: float | None, currency: str | None) -> float | None:
    """Convert to USD using configured rates; unknown currency -> None.

    Returning None is deliberate: a price in the wrong currency is worse than
    no price, because margin scoring would treat 229 EUR as 229 USD.
    """
    if amount is None or not currency:
        return None
    rate = config.usd_rates().get(currency.upper())
    if rate is None:
        log.warning("amazon: no FX rate for %s, dropping price", currency)
        return None
    return round(amount * rate, 2)


class AmazonProvider:
    name = "amazon"
    source = "amazon"

    def __init__(
        self,
        base_url: str = "",
        token: str = "",
        keywords: list[str] | None = None,
        sites: list[str] | None = None,
    ) -> None:
        self.base_url = (base_url or config.AMAZON_API_BASE).rstrip("/")
        self.token = token or config.AMAZON_TOKEN
        self.keywords = keywords if keywords is not None else config.amazon_keywords()
        self.sites = sites if sites is not None else config.amazon_sites()

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.token and self.keywords and self.sites)

    async def _get(self, client: httpx.AsyncClient, path: str, **params) -> dict[str, Any]:
        """GET with one retry — the aggregator drops connections sporadically."""
        last: Exception | None = None
        for attempt in (1, 2):
            try:
                response = await client.get(
                    f"{self.base_url}/{path}",
                    params={"token": self.token, "v": "1.0", **params},
                )
                response.raise_for_status()
                body = response.json()
                if body.get("code") == "success":
                    return body
                last = RuntimeError(body.get("msg") or body.get("code"))
            except Exception as exc:
                last = exc
            if attempt == 1:
                log.info("amazon: %s failed (%s), retrying once", path, last)
        raise last or RuntimeError("amazon request failed")

    async def fetch(self, limit: int = 50) -> list[RawProduct]:
        if not self.configured:
            log.warning("amazon: not configured, skipping")
            return []

        pairs = [(s, k) for s in self.sites for k in self.keywords]
        per_pair = max(1, limit // max(1, len(pairs)))
        products: list[RawProduct] = []

        async with httpx.AsyncClient(timeout=config.AMAZON_TIMEOUT) as client:
            for site, keyword in pairs:
                try:
                    body = await self._get(
                        client, "search/keyword", site=site, keyword=keyword, page=1
                    )
                except Exception as exc:
                    log.warning("amazon: %s/'%s' failed: %s", site, keyword, exc)
                    continue

                log.info(
                    "amazon: %s '%s' charged ¥%s, balance ¥%s",
                    site, keyword, body.get("charged_yuan"), body.get("balance_yuan"),
                )
                found = self.parse_search(body)
                log.info("amazon: %s '%s' -> %d products", site, keyword, len(found))
                products.extend(found[:per_pair])

        return products

    def parse_search(self, body: dict[str, Any]) -> list[RawProduct]:
        if body.get("code") != "success":
            log.error("amazon error: %s", body.get("msg") or body.get("code"))
            return []

        outer = body.get("data") or {}
        site = (outer.get("site") or "US").upper()
        inner = outer.get("data") or {}
        items = inner.get("items") or []

        products: list[RawProduct] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            asin = item.get("asin")
            title = (item.get("title") or "").strip()
            if not asin or not title:
                continue
            products.append(self._build(item, site, asin, title))
        return products

    def _build(self, item: dict[str, Any], site: str, asin: str, title: str) -> RawProduct:
        currency = (item.get("shipping") or {}).get("currency") or SITE_CURRENCY.get(site)
        price = to_usd(parse_number(item.get("price_text"), site), currency)

        tld = SITE_TLD.get(site, "com")
        return RawProduct(
            # The same ASIN exists on several marketplaces at different
            # prices, so the site must be part of the identity or US and DE
            # rows collide on the (source, external_id) unique index.
            external_id=f"{site}:{asin}",
            title=title,
            product_url=item.get("link") or f"https://www.amazon.{tld}/dp/{asin}",
            source=self.source,
            image_url=item.get("image") or (item.get("images") or [None])[0],
            category=(item.get("categories") or [None])[0],
            price_usd=price,
            cost_usd=None,       # Amazon is the retail anchor, not a supplier
            orders_count=None,   # Amazon publishes no sales count — see module docstring
            rating=parse_number(item.get("rating_text"), site),
        )

    def parse_detail(self, body: dict[str, Any]) -> RawProduct | None:
        """Detail returns one product in the same envelope as search."""
        if body.get("code") != "success":
            return None
        outer = body.get("data") or {}
        site = (outer.get("site") or "US").upper()
        item = outer.get("data") or {}
        asin, title = item.get("asin"), (item.get("title") or "").strip()
        if not asin or not title:
            return None
        return self._build(item, site, asin, title)
