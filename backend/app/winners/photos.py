"""Every pick gets a photo that really shows the product, stored by us.

Two problems this solves:

* Ad thumbnails from Facebook/TikTok are signed CDN links that expire after a
  few days, so a pick's picture used to turn into a placeholder icon.
* Ads are matched to products by their text. An ad whose words fit can still
  show something else, so the picture (and the "see the ad" link) could show a
  different item than the product name.

For each leading candidate, the photos available (the product's own image,
then the thumbnails of its verified ads, best first) are downloaded one by
one. With an AI key, the AI looks at each picture and says whether it shows
the product; the first one that does becomes the product photo, and its ad
becomes the ad linked from the pick. The photo is shrunk to a small JPEG,
stored in product_images and served from our API (/images/<id>.jpg), so it
never expires. A candidate with no photo of the product is not picked.
"""
from __future__ import annotations

import io
import logging
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin

import httpx

from app import config, db

from .collectors.base import AdRecord
from .llm import llm_available, llm_call
from .safe_fetch import UA, url_is_safe

log = logging.getLogger("winners.photos")

MAX_DOWNLOAD = 6_000_000       # bytes
MAX_SIDE = 720                 # px, longest side of the stored photo
MAX_TRIES = 4                  # photos tried per product
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
    for a in sorted(ads, key=lambda a: (a.platform != "meta", -(a.variant_count or 0))):
        add(a.thumbnail_url, key(a))
    return out


async def find_photo(name: str, image_url: Optional[str], ads: list[AdRecord]) -> tuple[Optional[Photo], bool]:
    """(photo, ai_checked). Tries up to MAX_TRIES pictures; the first the AI confirms wins.

    Without an AI verdict (no key / error) the first usable picture is used,
    as before, and ai_checked is False.
    """
    tried = 0
    fallback: Optional[Photo] = None
    for url, ad_key in candidates(image_url, ads):
        if tried >= MAX_TRIES:
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
            return photo, True
        if verdict is None and fallback is None:
            fallback = photo
    return fallback, False


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


async def ensure_photo(product_id: str, name: str, image_url: Optional[str], ads: list[AdRecord]) -> bool:
    """Make sure this product has a stored, checked photo. False = no photo of the product found."""
    have = await stored(product_id)
    if have and is_ours(image_url) and (have["age_days"] or 0) < REFRESH_DAYS \
            and (have["ai_checked"] or not llm_available()):
        return True
    photo, checked = await find_photo(name, None if is_ours(image_url) else image_url, ads)
    if photo is None:
        return bool(have) and is_ours(image_url) and not llm_available()
    await save(product_id, photo, checked)
    return True


async def get(product_id: str) -> Optional[tuple[bytes, str]]:
    row = await db.fetchrow("select data, content_type from product_images where product_id = $1", product_id)
    return (bytes(row["data"]), row["content_type"]) if row else None

