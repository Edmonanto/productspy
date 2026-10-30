"""
Price enrichment.

* Selling price: Shopify stores expose /products/<slug>.json for free — most
  dropshipping stores are Shopify. Otherwise read JSON-LD / og:price tags.
* Supplier cost: best-effort AliExpress search scrape; when it fails we use
  the AI estimate and mark the cost as *estimated* (the scorer trusts it less).
"""
from __future__ import annotations

import json
import os
import re
from statistics import median
from typing import Optional
from urllib.parse import quote_plus, urlparse

import httpx

from app import config

from .collectors.base import log


UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
      "Accept-Language": "en-US,en;q=0.9"}


def to_usd(amount: Optional[float], currency: Optional[str]) -> Optional[float]:
    """Convert with the app-wide rates (config.usd_rates).

    An unlisted currency returns None rather than pretending 229 EUR is
    229 USD — same rule as the Amazon provider.
    """
    if amount is None:
        return None
    rate = config.usd_rates().get((currency or "USD").upper())
    return round(amount * rate, 2) if rate else None


def sane_price(price: Optional[float]) -> Optional[float]:
    """Catch prices published in cents (6400 for 64.00).

    Some stores and themes print the minor unit — Shopify's .js endpoint, and
    JSON-LD written straight from {{ variant.price }} without dividing by 100.
    Read as-is, a $64 item becomes $6,400 and looks hugely profitable. A
    whole number of 1,000+ is read as cents when that gives a normal retail
    price; anything else that high is dropped rather than trusted.
    """
    if price is None or price <= 0:
        return None
    if price < MAX_PRICE:
        return price
    if float(price).is_integer() and 3 <= price / 100 <= 500:
        return round(price / 100, 2)
    return None


MAX_PRICE = 1000   # in the store's currency; dropshipping products sell far below this


def _variant_price(v) -> Optional[float]:
    raw = v.get("price")
    if raw in (None, ""):
        return None
    if isinstance(raw, int) and not isinstance(raw, bool):
        return raw / 100            # integer prices in Shopify JSON are cents (.js style)
    return _num(raw)


def parse_shopify_json(data: dict) -> Optional[dict]:
    p = data.get("product") or {}
    variants = p.get("variants") or []
    prices = [x for x in (_variant_price(v) for v in variants) if x]
    if not prices:
        return None
    img = (p.get("image") or {}).get("src") or ((p.get("images") or [{}])[0].get("src"))
    return {"price": min(prices), "currency": None, "title": p.get("title"), "image": img}


_LD_RE = re.compile(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', re.S | re.I)
_OG_PRICE = re.compile(r'<meta[^>]+(?:property|name)=["\'](?:og|product):price:amount["\'][^>]+content=["\']([\d.,]+)', re.I)
_OG_CUR = re.compile(r'<meta[^>]+(?:property|name)=["\'](?:og|product):price:currency["\'][^>]+content=["\']([A-Z]{3})', re.I)
_OG_IMG = re.compile(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', re.I)
_OG_TITLE = re.compile(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)', re.I)


def _num(s) -> Optional[float]:
    """64.00, 64,00, 1,299.00 and 1.299,00 all read correctly."""
    if isinstance(s, (int, float)) and not isinstance(s, bool):
        return float(s)
    t = str(s or "").strip().replace(" ", "").replace("\u00a0", "")
    if "," in t and "." in t:   # the last separator is the decimal one
        t = t.replace(",", "") if t.rfind(".") > t.rfind(",") else t.replace(".", "").replace(",", ".")
    elif "," in t:              # 1,299 = thousands; 64,00 = decimals
        t = t.replace(",", "") if len(t.rpartition(",")[2]) == 3 else t.replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def parse_product_html(html: str) -> Optional[dict]:
    for block in _LD_RE.findall(html):
        try:
            data = json.loads(block.strip())
        except ValueError:
            continue
        stack = [data]
        while stack:
            cur = stack.pop()
            if isinstance(cur, list):
                stack.extend(cur)
            elif isinstance(cur, dict):
                t = cur.get("@type")
                if t == "Product" or (isinstance(t, list) and "Product" in t):
                    offers = cur.get("offers") or {}
                    if isinstance(offers, list):
                        offers = offers[0] if offers else {}
                    price = _num(offers.get("price") or offers.get("lowPrice"))
                    if price:
                        img = cur.get("image")
                        if isinstance(img, list):
                            img = img[0] if img else None
                        if isinstance(img, dict):
                            img = img.get("url")
                        return {"price": price, "currency": offers.get("priceCurrency"),
                                "title": cur.get("name"), "image": img}
                stack.extend(v for v in cur.values() if isinstance(v, (dict, list)))
    m = _OG_PRICE.search(html)
    if m:
        cur = _OG_CUR.search(html)
        img = _OG_IMG.search(html)
        title = _OG_TITLE.search(html)
        return {"price": _num(m.group(1)), "currency": cur.group(1) if cur else None,
                "title": title.group(1) if title else None, "image": img.group(1) if img else None}
    return None


async def fetch_selling_price(url: Optional[str], market_currency: str = "USD") -> Optional[dict]:
    """Returns {"price_usd", "title", "image"} or None."""
    if not url or not url.startswith("http"):
        return None
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=UA) as c:
            p = urlparse(url)
            if "/products/" in p.path:
                base = f"{p.scheme}://{p.netloc}{p.path.rstrip('/')}"
                r = await c.get(base + ".json")
                if r.status_code == 200 and r.headers.get("content-type", "").startswith("application/json"):
                    info = parse_shopify_json(r.json())
                    if info:
                        info["price"] = sane_price(info["price"])
                        # Shopify .json is in the store's currency; assume market currency
                        info["price_usd"] = to_usd(info["price"], market_currency)
                        if info["price_usd"] is not None:
                            return info
            r = await c.get(url)
            if r.status_code == 200:
                info = parse_product_html(r.text)
                if info:
                    info["price"] = sane_price(info.get("price"))
                if info and info.get("price"):
                    info["price_usd"] = to_usd(info["price"], info.get("currency") or market_currency)
                    return info
    except Exception as e:
        log.debug("[enrich] price fetch failed for %s: %s", url, e)
    return None


_AE_PRICE = re.compile(r'"(?:minPrice|salePrice|minAmount)"\s*:\s*\{?[^0-9]{0,40}?([0-9]+\.[0-9]{1,2})')


def parse_aliexpress_prices(html: str) -> list[float]:
    vals = [float(v) for v in _AE_PRICE.findall(html)]
    return [v for v in vals if 0.3 <= v <= 300]


async def fetch_supplier_cost(product_name: str) -> Optional[dict]:
    """Median of the first AliExpress search prices. Best effort, free."""
    if not config.ENRICH_ALIEXPRESS:
        return None
    url = f"https://www.aliexpress.com/w/wholesale-{quote_plus(product_name.replace(' ', '-'))}.html?SortType=total_tranpro_desc"
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers=UA) as c:
            r = await c.get(url)
            if r.status_code != 200:
                return None
            prices = parse_aliexpress_prices(r.text)[:20]
            if len(prices) >= 3:
                return {"cost_usd": round(median(prices), 2), "supplier_url": url, "platform": "aliexpress"}
    except Exception as e:
        log.debug("[enrich] aliexpress failed for %s: %s", product_name, e)
    return None
