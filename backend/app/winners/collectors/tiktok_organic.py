"""
TikTok organic collector (free) — finds products going viral *before*
advertisers pile in.

Opens product-discovery hashtags (#tiktokmademebuyit, #amazonfinds ...) in
Playwright, reads the video JSON the page downloads (views, likes, shares,
comments, post time) and, for the most viral videos, samples comments to
count buying intent ("where can I buy", "link?", "c'est combien" ...).

TikTok results depend on the visitor's country: set PROXY_URL_<MARKET>
(e.g. PROXY_URL_AE) to a residential proxy in that country for accurate
local results. Without a proxy you get the server's country.
"""
from __future__ import annotations

import json
import os
from typing import Any, Iterable, Optional

from app import config
from app.winners.markets import Market
from .base import AdRecord, Collector, count_intent, log, to_dt, to_int

TAGS_BY_LANG = {
    "en": ["tiktokmademebuyit", "amazonfinds", "tiktokshopfinds", "musthaves", "viralproducts", "gadgets"],
    "fr": ["tiktokmafaitacheter", "trouvaille", "bonplan", "gadget", "tiktokmademebuyit"],
    "de": ["tiktokhatmichdazugebracht", "amazonfinds", "gadgets", "tiktokmademebuyit"],
    "ar": ["tiktokmademebuyit", "منتجات", "amazonfinds", "gadgets"],
}


def iter_videos(obj: Any) -> Iterable[dict]:
    stack = [obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            stats = cur.get("stats") or cur.get("statsV2")
            if isinstance(stats, dict) and "desc" in cur and "id" in cur and "author" in cur:
                yield cur
                continue
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)


def parse_video(v: dict, market: str) -> AdRecord:
    stats = v.get("stats") or {}
    stats2 = v.get("statsV2") or {}
    author = v.get("author") or {}
    handle = author.get("uniqueId") if isinstance(author, dict) else str(author)
    vid = str(v.get("id"))
    anchors = v.get("anchors") or []
    shop_link = None
    for a in anchors if isinstance(anchors, list) else []:
        extra = a.get("extraInfo") or {}
        shop_link = shop_link or a.get("schema") or extra.get("url")
    g = lambda k: to_int(stats.get(k)) if stats.get(k) is not None else to_int(stats2.get(k))
    return AdRecord(
        platform="tiktok_organic",
        external_id=vid,
        market=market,
        advertiser_name=handle,
        advertiser_id=str(author.get("id") or handle) if isinstance(author, dict) else handle,
        ad_text=v.get("desc"),
        landing_url=shop_link,
        thumbnail_url=(v.get("video") or {}).get("cover"),
        ad_url=f"https://www.tiktok.com/@{handle}/video/{vid}",
        started_at=to_dt(v.get("createTime")),
        views=g("playCount"),
        likes=g("diggCount"),
        comments=g("commentCount"),
        shares=g("shareCount"),
        raw={"saves": g("collectCount"), "has_anchor": bool(anchors)},
    )


class TikTokOrganicCollector(Collector):
    name = "tiktok_organic"

    def enabled(self) -> bool:
        return config.COLLECT_TIKTOK_ORGANIC

    def tags_for(self, market: Market) -> list[str]:
        override = os.getenv(f"TIKTOK_TAGS_{market.code}") or os.getenv("TIKTOK_TAGS")
        if override:
            return [t.strip().lstrip("#") for t in override.split(",") if t.strip()]
        return TAGS_BY_LANG.get(market.language, TAGS_BY_LANG["en"])

    async def collect(self, market: Market, limit: int = 150) -> list[AdRecord]:
        from playwright.async_api import async_playwright

        min_views = config.TIKTOK_MIN_VIEWS
        comment_samples = int(os.getenv("TIKTOK_COMMENT_SAMPLES", "15"))
        scrolls = int(os.getenv("TIKTOK_SCROLLS", "5"))
        proxy = self.proxy_for(market)
        out: dict[str, AdRecord] = {}
        comments_by_video: dict[str, list[str]] = {}

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True, proxy={"server": proxy} if proxy else None)
            ctx = await browser.new_context(
                locale="en-US", viewport={"width": 1280, "height": 900},
                user_agent=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"),
            )
            page = await ctx.new_page()

            async def on_response(resp):
                url = resp.url
                if "tiktok.com/api/" not in url:
                    return
                try:
                    blob = json.loads(await resp.text())
                except Exception:
                    return
                if "/api/comment/list" in url:
                    vid = None
                    for part in url.split("&"):
                        if "aweme_id=" in part:
                            vid = part.split("aweme_id=")[-1]
                    texts = [c.get("text", "") for c in (blob.get("comments") or []) if isinstance(c, dict)]
                    if vid:
                        comments_by_video.setdefault(vid, []).extend(texts)
                    return
                for v in iter_videos(blob):
                    rec = parse_video(v, market.code)
                    out.setdefault(rec.external_id, rec)

            page.on("response", on_response)

            for tag in self.tags_for(market):
                if len(out) >= limit * 2:
                    break
                try:
                    await page.goto(f"https://www.tiktok.com/tag/{tag}", wait_until="domcontentloaded",
                                    timeout=60_000)
                    await page.wait_for_timeout(3500)
                    # first batch is embedded in the HTML
                    raw = await page.locator("script#__UNIVERSAL_DATA_FOR_REHYDRATION__").all_inner_texts()
                    for txt in raw:
                        try:
                            for v in iter_videos(json.loads(txt)):
                                rec = parse_video(v, market.code)
                                out.setdefault(rec.external_id, rec)
                        except ValueError:
                            pass
                    for _ in range(scrolls):
                        await page.mouse.wheel(0, 4000)
                        await page.wait_for_timeout(1600)
                except Exception as e:
                    log.warning("[tiktok-organic] %s #%s failed: %s", market.code, tag, e)

            viral = [r for r in out.values() if (r.views or 0) >= min_views]
            viral.sort(key=lambda r: r.views or 0, reverse=True)
            for rec in viral[:comment_samples]:
                try:
                    await page.goto(rec.ad_url, wait_until="domcontentloaded", timeout=45_000)
                    await page.wait_for_timeout(3000)
                    await page.mouse.wheel(0, 1500)
                    await page.wait_for_timeout(1500)
                except Exception:
                    continue
                texts = comments_by_video.get(rec.external_id, [])
                if texts:
                    rec.sampled_comments = len(texts)
                    rec.intent_comments = count_intent(texts)
            await browser.close()

        viral = [r for r in out.values() if (r.views or 0) >= min_views]
        viral.sort(key=lambda r: r.views or 0, reverse=True)
        return viral[:limit]
