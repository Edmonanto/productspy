"""Every pick gets a photo that really shows the product, stored by us.

Two problems this solves:

* Ad thumbnails from Facebook/TikTok are signed CDN links that expire after a
  few days, so a pick's picture used to turn into a placeholder icon.
* Ads are matched to products by their text. An ad whose words fit can still
  show something else, so the picture (and the "see the ad" link) could show a
  different item than the product name.

For each leading candidate, the photos available (the product's own image,
then the pictures of its ads — thumbnails, then every carousel card/image —
best ad first) are downloaded one by one. When none of them shows the product
(links expired, or every picture is a person/logo), the store pages selling it
are opened (the product's URL and the ads' landing pages): Shopify's
/products/<slug>.json, then the page's JSON-LD product images and og:image. With an AI key, the AI looks at each picture and says whether it shows
the product; the first one that does becomes the product photo, and its ad
becomes the ad linked from the pick. The photo is shrunk to a small JPEG,
stored in product_images and served from our API (/images/<id>.jpg), so it
never expires. A candidate with no photo of the product is not picked.
"""
from __future__ import annotations

import io
import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx

from app import config, db

from .collectors.base import AdRecord
from .llm import llm_available, llm_call
from .safe_fetch import UA, fetch_text, url_is_safe

log = logging.getLogger("winners.photos")

MAX_DOWNLOAD = 6_000_000       # bytes
MAX_SIDE = 720                 # px, longest side of the stored photo
MAX_TRIES = 4                  # ad / own photos tried per product
STORE_TRIES = 4                # store-page photos tried when those fail
MAX_STORES = 3                 # store pages opened per product
NOT_STORES = ("facebook.com", "fb.com", "fb.me", "instagram.com", "tiktok.com", "youtube.com",
              "youtu.be", "linktr.ee", "bit.ly", "l.facebook.com")
REFRESH_DAYS = 30

SYSTEM = "You check product photos for an e-commerce research tool. You answer with strict JSON only."
PROMPT = """Does this picture clearly show this product: "{name}"?
Say true only if the product itself is visible (any brand, angle, model or background is fine).
Say false for a different item, a store logo or banner, a person with no product visible,
text only, or a picture too unclear to tell.
Return JSON: {{"match": true | false}}"""


@dataclass
class Photo:
    data: bytes
    content_type: str
    source_url: str
    ad_key: Optional[str]


def public_url(product_id: str) -> str:
    return f"{config.API_PUBLIC_URL}/images/{product_id}.jpg?v={int(time.time())}"


def is_ours(url: Optional[str]) -> bool:
    return bool(url) and url.startswith(f"{config.API_PUBLIC_URL}/images/")


async def download(url: str) -> Optional[tuple[bytes, str]]:
    """(bytes, content-type) of an image at a public URL, or None. Never raises."""
    if not url or not url.startswith("http"):
        return None
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=False, headers=UA) as client:
            for _ in range(4):
                if not await url_is_safe(url):
                    return None
                async with client.stream("GET", url) as resp:
                    if resp.status_code in (301, 302, 303, 307, 308) and resp.headers.get("location"):
                        url = urljoin(url, resp.headers["location"])
                        continue
                    ctype = resp.headers.get("content-type", "").split(";")[0].strip()
                    if resp.status_code != 200 or not ctype.startswith("image/"):
                        return None
                    buf = bytearray()
                    async for chunk in resp.aiter_bytes():
                        buf += chunk
                        if len(buf) > MAX_DOWNLOAD:
                            return None
                    return bytes(buf), ctype
    except Exception as exc:  # network, TLS, bad URL...
        log.debug("photo download failed for %s: %s", url[:120], exc)
    return None


def shrink(data: bytes) -> Optional[bytes]:
    """A small JPEG (longest side MAX_SIDE), or None if it isn't a usable picture."""
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(data))
        im.load()
    except Exception:
        return None
    if min(im.size) < 120:          # icons, tracking pixels
        return None
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[-1])
        im = bg
    elif im.mode != "RGB":
        im = im.convert("RGB")
    im.thumbnail((MAX_SIDE, MAX_SIDE))
    out = io.BytesIO()
    im.save(out, "JPEG", quality=82, optimize=True, progressive=True)
    return out.getvalue()


async def shows_product(name: str, jpeg: bytes) -> Optional[bool]:
    """True/False from the AI looking at the photo; None when it can't tell (no key, error)."""
    if not llm_available():
        return None
    res = await llm_call(SYSTEM, PROMPT.format(name=name), max_tokens=200, purpose="photo-check",
                         images=[(jpeg, "image/jpeg")])
    if isinstance(res.data, dict) and isinstance(res.data.get("match"), bool):
        return res.data["match"]
    return None


def candidates(image_url: Optional[str], ads: list[AdRecord], best: Optional[AdRecord] = None) -> list[tuple[str, Optional[str]]]:
    """(url, ad key) to try, in order: the product's own image, the best ad, other ads (Meta first)."""
    out: list[tuple[str, Optional[str]]] = []
    seen: set[str] = set()

    def add(url: Optional[str], key: Optional[str]) -> None:
        if url and url.startswith("http") and not is_ours(url) and url not in seen:
            seen.add(url)
            out.append((url, key))

    def key(a: AdRecord) -> str:
        return f"{a.platform}:{a.external_id}"

    add(image_url, None)
    if best is not None:
        add(best.thumbnail_url, key(best))
    ordered = sorted(ads, key=lambda a: (a.platform != "meta", -(a.variant_count or 0)))
    for a in ordered:
        add(a.thumbnail_url, key(a))
    for a in ordered:                       # then the ads' other pictures (carousel cards...)
        for url in (a.raw or {}).get("images") or []:
            add(url if isinstance(url, str) else None, key(a))
    return out


def store_pages(product_url: Optional[str], ads: list[AdRecord]) -> list[str]:
    """Store pages that sell the product: its own URL, then the ads' landing pages
    (product pages first), one per site, social/ad links skipped."""
    urls = [product_url] + [a.landing_url for a in
                            sorted(ads, key=lambda a: "/products/" not in (a.landing_url or ""))]
    out: list[str] = []
    hosts: set[str] = set()
    for u in urls:
        if not u or not u.startswith("http"):
            continue
        host = (urlparse(u).hostname or "").lower().removeprefix("www.")
        if not host or host in hosts or any(host == d or host.endswith("." + d) for d in NOT_STORES):
            continue
        hosts.add(host)
        out.append(u)
        if len(out) >= MAX_STORES:
            break
    return out


_LD = re.compile(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', re.S | re.I)
_META_IMG = re.compile(r'<meta[^>]+(?:property|name)=["\'](?:og:image(?::secure_url)?|twitter:image)["\'][^>]+'
                       r'content=["\']([^"\']+)', re.I)
_META_IMG_REV = re.compile(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']'
                           r'(?:og:image(?::secure_url)?|twitter:image)["\']', re.I)


def _abs(url: str, page: str) -> Optional[str]:
    url = (url or "").strip().replace("&amp;", "&")
    if url.startswith("//"):
        url = "https:" + url
    url = urljoin(page, url)
    return url if url.startswith("http") else None


def page_images(html: str, page_url: str, limit: int = 4) -> list[str]:
    """Product pictures on a store page: JSON-LD Product images first, then og:/twitter:image."""
    found: list[str] = []

    def add(u) -> None:
        if isinstance(u, dict):
            u = u.get("url") or u.get("contentUrl")
        a = _abs(u, page_url) if isinstance(u, str) else None
        if a and a not in found:
            found.append(a)

    for block in _LD.findall(html):
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
                    img = cur.get("image")
                    for u in (img if isinstance(img, list) else [img]):
                        add(u)
                stack.extend(v for v in cur.values() if isinstance(v, (dict, list)))
    metas = [(m.start(), m.group(1)) for rx in (_META_IMG, _META_IMG_REV) for m in rx.finditer(html)]
    for _, url in sorted(metas):            # in page order
        add(url)
    return found[:limit]


def shopify_images(data: dict, limit: int = 4) -> list[str]:
    p = data.get("product") if isinstance(data, dict) else None
    if not isinstance(p, dict):
        return []
    out = []
    for img in [p.get("image") or {}, *(p.get("images") or [])]:
        src = img.get("src") if isinstance(img, dict) else None
        if src:
            src = "https:" + src if src.startswith("//") else src
            if src not in out:
                out.append(src)
    return out[:limit]


async def store_images(page_url: str) -> list[str]:
    """Product pictures from one store page. Never raises; [] when nothing usable."""
    try:
        p = urlparse(page_url)
        if "/products/" in p.path:          # Shopify: the product's JSON lists every photo
            got = await fetch_text(f"{p.scheme}://{p.netloc}{p.path.rstrip('/')}.json")
            if got:
                try:
                    imgs = shopify_images(json.loads(got[1]))
                except ValueError:
                    imgs = []
                if imgs:
                    return imgs
        got = await fetch_text(page_url)
        return page_images(got[1], got[0]) if got else []
    except Exception as exc:
        log.debug("store page photos failed for %s: %s", page_url[:120], exc)
        return []


async def find_photo(name: str, image_url: Optional[str], ads: list[AdRecord],
                     product_url: Optional[str] = None) -> tuple[Optional[Photo], bool]:
    """(photo, ai_checked). Tries up to MAX_TRIES pictures from the product and its
    ads; the first the AI confirms wins. If none does, opens the store pages that
    sell it and tries up to STORE_TRIES of their product photos.

    Without an AI verdict (no key / error) the first usable picture is used,
    as before, and ai_checked is False.
    """
    fallback: Optional[Photo] = None

    async def attempt(urls: list[tuple[str, Optional[str]]], limit: int) -> Optional[Photo]:
        nonlocal fallback
        tried = 0
        for url, ad_key in urls:
            if tried >= limit:
                break
            got = await download(url)
            if not got:
                continue
            jpeg = shrink(got[0])
            if not jpeg:
                continue
            tried += 1
            verdict = await shows_product(name, jpeg)
            photo = Photo(jpeg, "image/jpeg", url, ad_key)
            if verdict is True:
                return photo
            if verdict is None and fallback is None:
                fallback = photo
        return None

    found = await attempt(candidates(image_url, ads), MAX_TRIES)
    if found:
        return found, True
    if fallback is None:     # nothing usable or every picture rejected: look on the store pages
        seen = {u for u, _ in candidates(image_url, ads)}
        store_urls: list[tuple[str, Optional[str]]] = []
        for page in store_pages(product_url, ads):
            for u in await store_images(page):
                if u not in seen:
                    seen.add(u)
                    store_urls.append((u, None))
            if len(store_urls) >= STORE_TRIES * 2:
                break
        found = await attempt(store_urls, STORE_TRIES)
        if found:
            return found, True
    return fallback, False


async def capture(product_id: str, image_url: Optional[str], ads: list[AdRecord]) -> bool:
    """Store the first usable picture right away, while its link still works
    (ad thumbnails expire within days). Not AI-checked yet: ensure_photo()
    checks it if the product becomes a pick candidate."""
    for url, ad_key in candidates(None if is_ours(image_url) else image_url, ads)[:MAX_TRIES]:
        got = await download(url)
        jpeg = shrink(got[0]) if got else None
        if jpeg:
            await save(product_id, Photo(jpeg, "image/jpeg", url, ad_key), False)
            return True
    return False


async def capture_step(market: str, stats: dict, limit: int = 200, parallel: int = 6) -> None:
    """Nightly, right after collection: save a photo for every new product."""
    import asyncio
    from . import store
    todo = await store.products_missing_photo(market, limit=limit)
    sem = asyncio.Semaphore(parallel)

    async def one(prod, ads) -> bool:
        async with sem:
            try:
                return await capture(str(prod["id"]), prod["image_url"], ads)
            except Exception:
                log.exception("photo capture failed for %s", prod["id"])
                return False

    done = await asyncio.gather(*(one(p, a) for p, a in todo))
    stats["photos_captured"] = sum(done)
    stats["photos_capture_missed"] = len(done) - sum(done)


async def save(product_id: str, photo: Photo, checked: bool) -> str:
    url = public_url(product_id)
    await db.execute(
        """
        insert into product_images (product_id, data, content_type, source_url, ai_checked, updated_at)
        values ($1, $2, $3, $4, $5, now())
        on conflict (product_id) do update set data = excluded.data, content_type = excluded.content_type,
            source_url = excluded.source_url, ai_checked = excluded.ai_checked, updated_at = now()
        """,
        product_id, photo.data, photo.content_type, photo.source_url, checked)
    await db.execute(
        """
        update products set image_url = $2, updated_at = now(),
               attributes = coalesce(attributes, '{}'::jsonb) || jsonb_build_object('photo_ad', $3::text)
         where id = $1
        """,
        product_id, url, photo.ad_key)
    return url


async def stored(product_id: str) -> Optional[dict]:
    return await db.fetchrow(
        "select ai_checked, updated_at, extract(day from now() - updated_at) as age_days "
        "from product_images where product_id = $1", product_id)


async def ensure_photo(product_id: str, name: str, image_url: Optional[str], ads: list[AdRecord],
                       product_url: Optional[str] = None) -> bool:
    """Make sure this product has a stored, checked photo. False = no photo of the product found."""
    have = await stored(product_id)
    if have and (have["age_days"] or 0) < REFRESH_DAYS and (have["ai_checked"] or not llm_available()):
        if not is_ours(image_url):      # products.image_url was replaced by an ad link: point it back
            await db.execute("update products set image_url = $2 where id = $1", product_id, public_url(product_id))
        return True
    photo, checked = await find_photo(name, None if is_ours(image_url) else image_url, ads, product_url)
    if photo is None:
        # No fresh picture shows it (links expired, or the AI said no) — fall back
        # to the one we stored when the product was new, checked now by the AI.
        if not have:
            return False
        if not llm_available():
            ok = True
        else:
            got = await get(product_id)
            verdict = await shows_product(name, got[0]) if got else None
            if verdict is True:
                await db.execute("update product_images set ai_checked = true, updated_at = now() "
                                 "where product_id = $1", product_id)
            ok = verdict is not False      # None = AI couldn't tell: keep the stored photo
        if ok and not is_ours(image_url):
            await db.execute("update products set image_url = $2 where id = $1", product_id, public_url(product_id))
        return ok
    await save(product_id, photo, checked)
    return True


async def get(product_id: str) -> Optional[tuple[bytes, str]]:
    row = await db.fetchrow("select data, content_type from product_images where product_id = $1", product_id)
    return (bytes(row["data"]), row["content_type"]) if row else None

