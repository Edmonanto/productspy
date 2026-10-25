"""
Facebook / Instagram Ad Library collector.

Two free modes, picked automatically per market:

1. Official Graph API  (EU markets — returns reach numbers, very reliable)
   Needs META_ACCESS_TOKEN from a Meta developer app that completed
   identity verification at facebook.com/ID. Commercial ads are only
   returned when they were delivered in the EU (Digital Services Act).

2. Web scraper (Playwright) for every other market (US, UK, AU, AE ...).
   Opens facebook.com/ads/library like a normal visitor, scrolls, and reads
   the JSON the page itself downloads. No login. Use a residential proxy for
   volume (PROXY_URL or PROXY_URL_<MARKET>).

For a paid, maintenance-free source switch on the Apify collector instead.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any, Iterable, Optional
from urllib.parse import quote_plus

import httpx

from app import config
from app.winners.markets import Market
from .base import AdRecord, Collector, log, to_dt, to_int, unwrap_redirect

def graph_url() -> str:
    return f"https://graph.facebook.com/{config.META_GRAPH_VERSION}/ads_archive"
API_FIELDS = ",".join([
    "id", "page_id", "page_name", "ad_creation_time", "ad_delivery_start_time",
    "ad_delivery_stop_time", "ad_creative_bodies", "ad_creative_link_titles",
    "ad_creative_link_captions", "ad_creative_link_descriptions", "ad_snapshot_url",
    "publisher_platforms", "eu_total_reach", "languages",
])
_DOMAIN_RE = re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)+$", re.I)


# ---------------------------------------------------------------- API mode

def parse_api_ad(item: dict, market: str) -> AdRecord:
    bodies = item.get("ad_creative_bodies") or []
    titles = item.get("ad_creative_link_titles") or []
    captions = item.get("ad_creative_link_captions") or []
    caption = (captions[0] if captions else "") or ""
    landing = f"https://{caption.lower()}" if _DOMAIN_RE.match(caption.strip()) else None
    text = " | ".join(filter(None, [titles[0] if titles else None, bodies[0] if bodies else None]))
    return AdRecord(
        platform="meta",
        external_id=str(item.get("id")),
        market=market,
        advertiser_name=item.get("page_name"),
        advertiser_id=str(item.get("page_id") or ""),
        ad_text=text or None,
        landing_url=landing,
        ad_url=item.get("ad_snapshot_url"),
        started_at=to_dt(item.get("ad_delivery_start_time") or item.get("ad_creation_time")),
        is_active=not item.get("ad_delivery_stop_time"),
        reach=to_int(item.get("eu_total_reach")),
        raw={k: item.get(k) for k in ("publisher_platforms", "languages", "ad_creative_link_titles")},
    )


async def _collect_api(market: Market, limit: int) -> list[AdRecord]:
    token = config.META_ACCESS_TOKEN
    GRAPH_URL = graph_url()
    out: dict[str, AdRecord] = {}
    per_term = max(25, limit // max(1, len(market.search_terms)))
    async with httpx.AsyncClient(timeout=40) as client:
        for term in market.search_terms:
            params = {
                "access_token": token,
                "search_terms": term,
                "ad_type": "ALL",
                "ad_active_status": "ACTIVE",
                "ad_reached_countries": json.dumps(list(market.meta_countries)),
                "fields": API_FIELDS,
                "limit": 100,
            }
            url: Optional[str] = GRAPH_URL
            got = 0
            while url and got < per_term:
                resp = await client.get(url, params=params if url == GRAPH_URL else None)
                if resp.status_code != 200:
                    log.warning("[meta-api] %s term=%r: %s", resp.status_code, term, resp.text[:300])
                    break
                payload = resp.json()
                for item in payload.get("data", []):
                    rec = parse_api_ad(item, market.code)
                    out.setdefault(rec.external_id, rec)
                    got += 1
                url = (payload.get("paging") or {}).get("next")
                await asyncio.sleep(0.5)
            if len(out) >= limit:
                break
    return list(out.values())[:limit]


# ---------------------------------------------------------------- web mode

def iter_ad_nodes(obj: Any) -> Iterable[dict]:
    """Walk any JSON blob and yield every dict that looks like a library ad."""
    stack = [obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            if "ad_archive_id" in cur and isinstance(cur.get("snapshot"), dict):
                yield cur
                continue
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)


def parse_web_ad(node: dict, market: str) -> AdRecord:
    snap = node.get("snapshot") or {}
    cards = snap.get("cards") or []
    first_card = cards[0] if cards else {}
    body = (snap.get("body") or {}).get("text") if isinstance(snap.get("body"), dict) else snap.get("body")
    title = snap.get("title") or first_card.get("title")
    link = unwrap_redirect(snap.get("link_url") or first_card.get("link_url"))
    videos = snap.get("videos") or first_card.get("videos") or []
    images = snap.get("images") or []
    thumb = None
    media = None
    if videos:
        v = videos[0]
        thumb = v.get("video_preview_image_url")
        media = v.get("video_hd_url") or v.get("video_sd_url")
    if not thumb:
        thumb = (images[0].get("resized_image_url") or images[0].get("original_image_url")) if images else (
            first_card.get("resized_image_url") or first_card.get("original_image_url"))
    ad_id = str(node.get("ad_archive_id"))
    return AdRecord(
        platform="meta",
        external_id=ad_id,
        market=market,
        advertiser_name=node.get("page_name") or snap.get("page_name"),
        advertiser_id=str(node.get("page_id") or snap.get("page_id") or ""),
        ad_text=" | ".join(filter(None, [title, body])) or None,
        landing_url=link,
        media_url=media,
        thumbnail_url=thumb,
        ad_url=f"https://www.facebook.com/ads/library/?id={ad_id}",
        started_at=to_dt(node.get("start_date")),
        is_active=bool(node.get("is_active", True)),
        variant_count=to_int(node.get("collation_count")) or 1,
        reach=to_int((node.get("reach_estimate") or None)),
        raw={"cta": snap.get("cta_text"), "caption": snap.get("caption"),
             "platforms": node.get("publisher_platform")},
    )


def library_url(country: str, term: str) -> str:
    return (
        "https://www.facebook.com/ads/library/?active_status=active&ad_type=all"
        f"&country={country}&q={quote_plus(term)}&search_type=keyword_unordered&media_type=all"
    )


async def _collect_web(market: Market, limit: int, proxy: Optional[str]) -> list[AdRecord]:
    from playwright.async_api import async_playwright  # lazy import

    out: dict[str, AdRecord] = {}
    scrolls = int(os.getenv("META_WEB_SCROLLS", "8"))

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True, proxy={"server": proxy} if proxy else None,
        )
        ctx = await browser.new_context(locale="en-US", viewport={"width": 1366, "height": 900})
        page = await ctx.new_page()

        async def on_response(resp):
            if "/api/graphql" not in resp.url:
                return
            try:
                text = await resp.text()
            except Exception:
                return
            for line in text.splitlines():  # graphql may stream several JSON docs
                try:
                    blob = json.loads(line)
                except ValueError:
                    continue
                for node in iter_ad_nodes(blob):
                    rec = parse_web_ad(node, market.code)
                    out.setdefault(rec.external_id, rec)

        page.on("response", on_response)

        for term in market.search_terms:
            if len(out) >= limit:
                break
            country = market.meta_countries[0]
            try:
                await page.goto(library_url(country, term), wait_until="domcontentloaded", timeout=60_000)
                await page.wait_for_timeout(3500)
                # first results are embedded in the HTML as JSON
                for blob_text in await page.locator('script[type="application/json"]').all_inner_texts():
                    try:
                        for node in iter_ad_nodes(json.loads(blob_text)):
                            rec = parse_web_ad(node, market.code)
                            out.setdefault(rec.external_id, rec)
                    except ValueError:
                        continue
                for _ in range(scrolls):
                    await page.mouse.wheel(0, 6000)
                    await page.wait_for_timeout(1800)
                    if len(out) >= limit:
                        break
            except Exception as e:  # keep going with the next term
                log.warning("[meta-web] %s term=%r failed: %s", market.code, term, e)
        await browser.close()
    return list(out.values())[:limit]


class MetaAdLibraryCollector(Collector):
    name = "meta_ad_library"

    def enabled(self) -> bool:
        return config.COLLECT_META

    async def collect(self, market: Market, limit: int = 200) -> list[AdRecord]:
        if market.meta_api_ok and config.META_ACCESS_TOKEN:
            log.info("[meta] %s via official API", market.code)
            recs = await _collect_api(market, limit)
            if recs:
                return recs
        if not config.META_WEB_SCRAPER:
            return []
        log.info("[meta] %s via web scraper", market.code)
        return await _collect_web(market, limit, self.proxy_for(market))
