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
import time
from datetime import date
from typing import Any

import httpx

from app import config
from app.winners.markets import Market
from .base import AdRecord, Collector, log, to_dt, to_int
from .meta_ads import iter_ad_nodes, library_url, parse_web_ad
from .tiktok_ads import iter_materials, parse_material, parse_top_ad
from .tiktok_organic import TikTokOrganicCollector

APIFY_RUN = "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"

LIMIT_HELP = ("Apify account limit reached ({detail}). Nothing can be scraped until it resets or the limit "
              "is raised: console.apify.com → Settings → Usage & limits (or upgrade the plan).")


class ApifyLimitError(RuntimeError):
    """The Apify account is blocked (monthly hard limit, no credit). Every actor fails until fixed."""


_blocked: str | None = None   # remembered for the rest of the run: no point calling again


def _check_blocked(status: int, text: str) -> None:
    global _blocked
    low = text.lower()
    if status in (402, 403) and ("limit" in low or "platform-feature-disabled" in low or "credit" in low):
        detail = "monthly usage hard limit exceeded" if "hard limit" in low else "account disabled or out of credit"
        _blocked = LIMIT_HELP.format(detail=detail)
        raise ApifyLimitError(_blocked)


BUDGET_HELP = ("Apify monthly budget reached: ${used:.2f} used of ${budget:.0f} (APIFY_MONTHLY_BUDGET_USD). "
               "Scraping is paused until the Apify billing cycle resets on {reset}.")
_usage_cache: tuple[float, float, str] | None = None   # (checked_at, used_usd, cycle_end)
USAGE_CACHE_SECONDS = 300


async def _monthly_usage() -> tuple[float, str] | None:
    """(USD used this billing cycle, cycle end date) from Apify, cached for 5 min. None if unknown."""
    global _usage_cache
    if _usage_cache and time.monotonic() - _usage_cache[0] < USAGE_CACHE_SECONDS:
        return _usage_cache[1], _usage_cache[2]
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get("https://api.apify.com/v2/users/me/limits",
                                 headers={"Authorization": f"Bearer {config.APIFY_TOKEN}"})
        if r.status_code >= 300:
            return None
        data = r.json().get("data") or {}
        used = float((data.get("current") or {}).get("monthlyUsageUsd") or 0)
        reset = str((data.get("monthlyUsageCycle") or {}).get("endAt") or "")[:10] or "the next cycle"
    except Exception as exc:  # unknown usage must not stop the run
        log.warning("[apify] could not read monthly usage: %s", exc)
        return None
    _usage_cache = (time.monotonic(), used, reset)
    return used, reset


async def _check_budget() -> None:
    """Raise ApifyLimitError once this cycle's usage reaches APIFY_MONTHLY_BUDGET_USD."""
    global _blocked
    budget = config.APIFY_MONTHLY_BUDGET_USD
    if budget <= 0:
        return
    got = await _monthly_usage()
    if got is None:
        return
    used, reset = got
    if used >= budget:
        _blocked = BUDGET_HELP.format(used=used, budget=budget, reset=reset)
        raise ApifyLimitError(_blocked)


async def run_actor(actor: str, payload: dict, timeout: int = 600) -> list[Any]:
    """Run an actor synchronously and return its dataset. Metered and capped
    (app/usage.py); the token goes in a header, never in a logged URL."""
    from app import usage

    if _blocked:
        raise ApifyLimitError(_blocked)
    await _check_budget()
    if not await usage.allowed("apify"):
        return []
    endpoint = actor.split("~")[-1].split("/")[-1][:60]
    try:
        async with httpx.AsyncClient(timeout=timeout + 30) as client:
            resp = await client.post(
                APIFY_RUN.format(actor=actor.replace("/", "~")),
                headers={"Authorization": f"Bearer {config.APIFY_TOKEN}"},
                params={"timeout": timeout},
                json=payload,
            )
    except httpx.HTTPError as exc:
        await usage.record("apify", endpoint, ok=False, error=f"network: {exc}")
        raise
    if resp.status_code >= 300:
        log.warning("[apify] %s -> %s %s", actor, resp.status_code, resp.text[:300])
        await usage.record("apify", endpoint, ok=False, error=f"{resp.status_code} {resp.text[:200]}")
        _check_blocked(resp.status_code, resp.text)
        return []
    data = resp.json()
    items = data if isinstance(data, list) else []
    await usage.record("apify", endpoint, ok=True, items=len(items))
    return items


async def run_actor_async(actor: str, payload: dict, max_wait: int = 900, keep_partial: bool = False) -> list[Any]:
    """Start a run, poll until it finishes (up to max_wait s), return its dataset.
    For actors that can take longer than run-sync's ~5 minute limit. Metered like run_actor."""
    import asyncio

    from app import usage

    if _blocked:
        raise ApifyLimitError(_blocked)
    await _check_budget()
    if not await usage.allowed("apify"):
        return []
    endpoint = actor.split("~")[-1].split("/")[-1][:60]
    headers = {"Authorization": f"Bearer {config.APIFY_TOKEN}"}
    base = "https://api.apify.com/v2"
    async with httpx.AsyncClient(timeout=90) as client:
        r = await client.post(f"{base}/acts/{actor.replace('/', '~')}/runs", headers=headers,
                              params={"waitForFinish": 60}, json=payload)
        if r.status_code >= 300:
            await usage.record("apify", endpoint, ok=False, error=f"{r.status_code} {r.text[:200]}")
            log.warning("[apify] %s -> %s %s", actor, r.status_code, r.text[:300])
            _check_blocked(r.status_code, r.text)
            return []
        run = r.json().get("data") or {}
        waited = 60
        while run.get("status") in ("READY", "RUNNING") and waited < max_wait:
            r = await client.get(f"{base}/actor-runs/{run['id']}", headers=headers, params={"waitForFinish": 60})
            run = r.json().get("data") or run
            waited += 60
        if run.get("status") != "SUCCEEDED":
            await usage.record("apify", endpoint, ok=False, error=f"run {run.get('status')}")
            log.warning("[apify] %s run ended %s", actor, run.get("status"))
            if run.get("status") in ("READY", "RUNNING"):
                await client.post(f"{base}/actor-runs/{run['id']}/abort", headers=headers)
            if not (keep_partial and run.get("defaultDatasetId")):
                return []
            # Paid for already: keep whatever the run finished before it was stopped.
            r = await client.get(f"{base}/datasets/{run['defaultDatasetId']}/items", headers=headers,
                                 params={"clean": "true", "format": "json"})
            items = r.json() if r.status_code < 300 else []
            items = items if isinstance(items, list) else []
            log.info("[apify] %s kept %d items from the stopped run", actor, len(items))
            return items
        r = await client.get(f"{base}/datasets/{run['defaultDatasetId']}/items", headers=headers,
                             params={"clean": "true", "format": "json"})
        items = r.json() if r.status_code < 300 else []
    items = items if isinstance(items, list) else []
    await usage.record("apify", endpoint, ok=True, items=len(items))
    return items


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


async def refresh_tiktok_videos(urls: list[str], market: str) -> dict[str, AdRecord]:
    """Fresh data (cover image included) for specific TikTok videos, by id.
    Stored cover links are signed and expire within days."""
    if not (urls and _apify_on()):
        return {}
    items = await run_actor(config.APIFY_TIKTOK_ACTOR, {
        "postURLs": urls, "resultsPerPage": 1,
        "shouldDownloadVideos": False, "shouldDownloadCovers": False,
    })
    out: dict[str, AdRecord] = {}
    for it in items if isinstance(items, list) else []:
        if isinstance(it, dict) and it.get("id"):
            rec = parse_apify_tiktok(it, market)
            if rec.thumbnail_url:
                out[rec.external_id] = rec
    return out


class ApifyMetaCollector(Collector):
    name = "apify_meta"
    paid = True

    def enabled(self) -> bool:
        return _apify_on()

    async def collect(self, market: Market, limit: int | None = None) -> list[AdRecord]:
        actor = config.APIFY_META_ACTOR
        limit = limit or config.APIFY_META_MAX
        # "count" is the TOTAL for the run (the actor stops once it has that many
        # ads — "Scraped requested number of records"), not a per-URL limit:
        # passing limit/len(urls) capped every market at ~25 ads a night.
        # The actor works through the URLs in order, so rotate them daily and a
        # different search phrase leads each night.
        terms = list(market.search_terms)
        if terms:
            k = date.today().toordinal() % len(terms)
            terms = terms[k:] + terms[:k]
        urls = [{"url": library_url(c, t)} for c in market.meta_countries[:1] for t in terms]
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

    async def collect(self, market: Market, limit: int | None = None) -> list[AdRecord]:
        actor = config.APIFY_TIKTOK_ACTOR
        limit = limit or config.APIFY_TIKTOK_MAX
        tags = TikTokOrganicCollector().tags_for(market)[:6]
        items = await run_actor(actor, {
            "hashtags": tags,
            "resultsPerPage": max(10, limit // max(1, len(tags))),
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

    async def collect(self, market: Market, limit: int | None = None) -> list[AdRecord]:
        limit = limit or config.APIFY_TIKTOK_ADS_MAX
        # Product-sales ads only (no apps/games/leads), with details: the
        # landing page is the store we read the selling price from.
        items = await run_actor(config.APIFY_TIKTOK_ADS_ACTOR, {
            "countryCode": market.tiktok_regions[0], "period": str(config.TIKTOK_CC_PERIOD),
            "maxItems": max(10, limit), "extractDetails": True,
            "objective": "campaign_objective_product_sales", "orderBy": "for_you",
        })
        out: dict[str, AdRecord] = {}
        for it in items if isinstance(items, list) else []:
            rec = parse_top_ad(it, market.code) if isinstance(it, dict) and "adId" in it else None
            if rec:
                out.setdefault(rec.external_id, rec)
        for mat in iter_materials(items):          # older snake_case actors
            rec = parse_material(mat, market.code)
            if rec:
                out.setdefault(rec.external_id, rec)
        return list(out.values())[:limit]
