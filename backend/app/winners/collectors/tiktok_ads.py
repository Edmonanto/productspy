"""
TikTok Creative Center — "Top Ads" collector (free, no login).

ads.tiktok.com/business/creativecenter/inspiration/topads lists the best
performing paid ads per region with CTR, likes and a budget level. The page
calls a signed internal API, so instead of re-implementing the signature we
open the page in Playwright and read the JSON responses it receives.
For the top N ads we also open the detail page to get the landing page URL.
"""
from __future__ import annotations

import json
import os
from typing import Any, Iterable, Optional

from app import config
from app.winners.markets import Market
from .base import AdRecord, Collector, log, to_dt, to_int

CC_LIST_URL = (
    "https://ads.tiktok.com/business/creativecenter/inspiration/topads/pc/en"
    "?period={period}&region={region}&sort_by=like"
)
CC_DETAIL_URL = (
    "https://ads.tiktok.com/business/creativecenter/topads/{id}/pc/en"
    "?countryCode={region}&from=001110&period={period}"
)
# objectives that are not physical-product selling
_SKIP_OBJECTIVES = ("app", "lead", "reach", "follower", "community")


def iter_materials(obj: Any) -> Iterable[dict]:
    stack = [obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            if "ad_title" in cur and "id" in cur and ("ctr" in cur or "like" in cur):
                yield cur
                continue
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)


def _norm_ctr(v) -> Optional[float]:
    if v in (None, ""):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f / 100 if f > 1 else f   # API sometimes returns 3.1 (=%) sometimes 0.031


def parse_material(m: dict, market: str) -> Optional[AdRecord]:
    objective = str(m.get("objective_key") or m.get("objective") or "").lower()
    if any(s in objective for s in _SKIP_OBJECTIVES):
        return None
    video = m.get("video_info") or {}
    vurl = video.get("video_url") or {}
    media = None
    if isinstance(vurl, dict):
        media = vurl.get("720p") or vurl.get("540p") or next(iter(vurl.values()), None)
    elif isinstance(vurl, str):
        media = vurl
    mid = str(m.get("id"))
    return AdRecord(
        platform="tiktok_ads",
        external_id=mid,
        market=market,
        advertiser_name=m.get("brand_name"),
        ad_text=m.get("ad_title"),
        landing_url=m.get("landing_page"),
        media_url=media,
        thumbnail_url=video.get("cover"),
        ad_url=f"https://ads.tiktok.com/business/creativecenter/topads/{mid}/pc/en",
        started_at=to_dt(m.get("first_shown_date") or m.get("create_time")),
        likes=to_int(m.get("like")),
        comments=to_int(m.get("comment")),
        shares=to_int(m.get("share")),
        ctr=_norm_ctr(m.get("ctr")),
        budget_level=to_int(m.get("cost")),
        raw={"industry": m.get("industry_key"), "objective": objective,
             "keywords": m.get("keyword_list"), "duration": video.get("duration")},
    )


class TikTokCreativeCenterCollector(Collector):
    name = "tiktok_creative_center"

    def enabled(self) -> bool:
        return config.COLLECT_TIKTOK_ADS

    async def collect(self, market: Market, limit: int = 120) -> list[AdRecord]:
        from playwright.async_api import async_playwright

        period = config.TIKTOK_CC_PERIOD
        details = int(os.getenv("TIKTOK_CC_DETAILS", "20"))  # landing pages to fetch
        scrolls = int(os.getenv("TIKTOK_CC_SCROLLS", "6"))
        proxy = self.proxy_for(market)
        out: dict[str, AdRecord] = {}
        detail_payloads: dict[str, dict] = {}

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True, proxy={"server": proxy} if proxy else None)
            ctx = await browser.new_context(locale="en-US", viewport={"width": 1366, "height": 900})
            page = await ctx.new_page()

            async def on_response(resp):
                if "creative_radar_api" not in resp.url:
                    return
                try:
                    blob = json.loads(await resp.text())
                except Exception:
                    return
                if "/detail" in resp.url:
                    data = (blob.get("data") or {})
                    if data.get("id"):
                        detail_payloads[str(data["id"])] = data
                    return
                for mat in iter_materials(blob):
                    rec = parse_material(mat, market.code)
                    if rec:
                        out.setdefault(rec.external_id, rec)

            page.on("response", on_response)

            for region in market.tiktok_regions:
                if len(out) >= limit:
                    break
                try:
                    await page.goto(CC_LIST_URL.format(period=period, region=region),
                                    wait_until="domcontentloaded", timeout=60_000)
                    await page.wait_for_timeout(4000)
                    for _ in range(scrolls):
                        # the list has a "View more" button rather than infinite scroll
                        more = page.get_by_text("View More", exact=False)
                        if await more.count():
                            try:
                                await more.first.click(timeout=3000)
                            except Exception:
                                pass
                        await page.mouse.wheel(0, 5000)
                        await page.wait_for_timeout(1800)
                        if len(out) >= limit:
                            break
                except Exception as e:
                    log.warning("[tiktok-cc] %s/%s failed: %s", market.code, region, e)

            # landing pages for the best ads (by likes)
            best = sorted(out.values(), key=lambda r: (r.likes or 0), reverse=True)[:details]
            for rec in best:
                if rec.landing_url:
                    continue
                try:
                    await page.goto(CC_DETAIL_URL.format(id=rec.external_id, region=market.tiktok_regions[0],
                                                         period=period),
                                    wait_until="domcontentloaded", timeout=45_000)
                    await page.wait_for_timeout(2500)
                except Exception as e:
                    log.debug("[tiktok-cc] detail %s failed: %s", rec.external_id, e)
                d = detail_payloads.get(rec.external_id)
                if d:
                    rec.landing_url = d.get("landing_page") or rec.landing_url
                    rec.ctr = rec.ctr or _norm_ctr(d.get("ctr"))
            await browser.close()

        return list(out.values())[:limit]
