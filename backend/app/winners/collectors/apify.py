"""
Paid collectors via Apify (switch on when the free scrapers get blocked).

Set APIFY_TOKEN and USE_APIFY=true. Actor IDs are configurable because Apify
actors come and go — defaults are popular, well-maintained ones:

  APIFY_META_ACTOR        curious_coder~facebook-ads-library-scraper
  APIFY_TIKTOK_ACTOR      clockworks~tiktok-scraper
  APIFY_TIKTOK_ADS_ACTOR  (optional) any Creative Center "top ads" actor

When enabled, these replace the matching free collector for every market.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

from app import config
from app.winners.markets import Market
from .base import AdRecord, Collector, log, to_dt, to_int
from .meta_ads import iter_ad_nodes, library_url, parse_web_ad
from .tiktok_ads import iter_materials, parse_material
from .tiktok_organic import TikTokOrganicCollector

APIFY_RUN = "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"


async def run_actor(actor: str, payload: dict, timeout: int = 600) -> list[Any]:
    token = config.APIFY_TOKEN
    async with httpx.AsyncClient(timeout=timeout + 30) as client:
        resp = await client.post(
            APIFY_RUN.format(actor=actor.replace("/", "~")),
            params={"token": token, "timeout": timeout},
            json=payload,
        )
        if resp.status_code >= 300:
            log.warning("[apify] %s -> %s %s", actor, resp.status_code, resp.text[:300])
            return []
        data = resp.json()
        return data if isinstance(data, list) else []


def _apify_on() -> bool:
    return config.USE_APIFY and bool(config.APIFY_TOKEN)


def parse_apify_tiktok(item: dict, market: str) -> AdRecord:
    author = item.get("authorMeta") or {}
    vid = str(item.get("id"))
    return AdRecord(
        platform="tiktok_organic",
        external_id=vid,
        market=market,
        advertiser_name=author.get("name") or author.get("nickName"),
        advertiser_id=str(author.get("id") or author.get("name") or ""),
        ad_text=item.get("text"),
        thumbnail_url=(item.get("videoMeta") or {}).get("coverUrl"),
        ad_url=item.get("webVideoUrl"),
        started_at=to_dt(item.get("createTimeISO") or item.get("createTime")),
        views=to_int(item.get("playCount")),
        likes=to_int(item.get("diggCount")),
        comments=to_int(item.get("commentCount")),
        shares=to_int(item.get("shareCount")),
        raw={"saves": to_int(item.get("collectCount"))},
    )


class ApifyMetaCollector(Collector):
    name = "apify_meta"
    paid = True

    def enabled(self) -> bool:
        return _apify_on()

    async def collect(self, market: Market, limit: int = 300) -> list[AdRecord]:
        actor = config.APIFY_META_ACTOR
        urls = [{"url": library_url(c, t)} for c in market.meta_countries[:2] for t in market.search_terms]
        items = await run_actor(actor, {"urls": urls, "count": limit, "scrapeAdDetails": False})
        out: dict[str, AdRecord] = {}
        for node in iter_ad_nodes(items):
            rec = parse_web_ad(node, market.code)
            out.setdefault(rec.external_id, rec)
        return list(out.values())[:limit]


class ApifyTikTokCollector(Collector):
    name = "apify_tiktok"
    paid = True

    def enabled(self) -> bool:
        return _apify_on()

    async def collect(self, market: Market, limit: int = 300) -> list[AdRecord]:
        actor = config.APIFY_TIKTOK_ACTOR
        tags = TikTokOrganicCollector().tags_for(market)
        items = await run_actor(actor, {
            "hashtags": tags,
            "resultsPerPage": max(20, limit // max(1, len(tags))),
            "proxyCountryCode": market.tiktok_regions[0],
            "shouldDownloadVideos": False,
            "shouldDownloadCovers": False,
        })
        recs = [parse_apify_tiktok(i, market.code) for i in items if isinstance(i, dict) and i.get("id")]
        min_views = config.TIKTOK_MIN_VIEWS
        recs = [r for r in recs if (r.views or 0) >= min_views]
        recs.sort(key=lambda r: r.views or 0, reverse=True)
        return recs[:limit]


class ApifyTikTokAdsCollector(Collector):
    name = "apify_tiktok_ads"
    paid = True

    def enabled(self) -> bool:
        return _apify_on() and bool(config.APIFY_TIKTOK_ADS_ACTOR)

    async def collect(self, market: Market, limit: int = 200) -> list[AdRecord]:
        items = await run_actor(config.APIFY_TIKTOK_ADS_ACTOR, {
            "region": market.tiktok_regions[0], "period": int(config.TIKTOK_CC_PERIOD),
            "maxItems": limit,
        })
        out = {}
        for mat in iter_materials(items):
            rec = parse_material(mat, market.code)
            if rec:
                out.setdefault(rec.external_id, rec)
        return list(out.values())[:limit]
