"""Pick photos: the AI must confirm the picture shows the product; photos are stored by us."""
import io

import pytest
from PIL import Image

from app.winners import llm, photos
from app.winners.collectors.base import AdRecord


def _ad(i, thumb, platform="meta", variants=1):
    return AdRecord(platform=platform, external_id=str(i), market="US", thumbnail_url=thumb, variant_count=variants)


def _jpeg(w=400, h=300, mode="RGB"):
    out = io.BytesIO()
    Image.new(mode, (w, h), (200, 30, 30, 255) if mode == "RGBA" else (200, 30, 30)).save(out, "PNG")
    return out.getvalue()


def test_candidates_order_and_dedupe():
    ads = [_ad(1, "https://x/t1.jpg", "tiktok_ads", 9), _ad(2, "https://x/m2.jpg", "meta", 1),
           _ad(3, "https://x/m3.jpg", "meta", 5), _ad(4, "https://x/m3.jpg", "meta", 2), _ad(5, None)]
    c = photos.candidates("https://store/p.jpg", ads)
    assert [u for u, _ in c] == ["https://store/p.jpg", "https://x/m3.jpg", "https://x/m2.jpg", "https://x/t1.jpg"]
    assert c[0][1] is None and c[1][1] == "meta:3"


def test_candidates_skip_our_own_url(monkeypatch):
    monkeypatch.setattr(photos.config, "API_PUBLIC_URL", "https://api.test/api/v1")
    assert photos.candidates("https://api.test/api/v1/images/abc.jpg?v=1", []) == []


def test_shrink_makes_small_jpeg_and_rejects_icons():
    out = photos.shrink(_jpeg(2000, 1000, "RGBA"))
    im = Image.open(io.BytesIO(out))
    assert im.format == "JPEG" and max(im.size) == photos.MAX_SIDE
    assert photos.shrink(_jpeg(60, 60)) is None
    assert photos.shrink(b"not an image") is None


@pytest.mark.asyncio
async def test_first_confirmed_photo_wins(monkeypatch):
    ads = [_ad(1, "https://x/a.jpg"), _ad(2, "https://x/b.jpg")]

    async def dl(url):
        return _jpeg(), "image/png"
    seen = []

    async def ai(name, jpeg):
        seen.append(name)
        return len(seen) == 2          # first picture: no; second: yes
    monkeypatch.setattr(photos, "download", dl)
    monkeypatch.setattr(photos, "shows_product", ai)
    photo, checked = await photos.find_photo("Ski Guards", None, ads)
    assert checked and photo.source_url == "https://x/b.jpg" and photo.ad_key == "meta:2"


@pytest.mark.asyncio
async def test_no_photo_when_ai_rejects_all(monkeypatch):
    async def dl(url):
        return _jpeg(), "image/png"

    async def ai(name, jpeg):
        return False
    monkeypatch.setattr(photos, "download", dl)
    monkeypatch.setattr(photos, "shows_product", ai)
    photo, checked = await photos.find_photo("Ski Guards", "https://store/p.jpg", [_ad(1, "https://x/a.jpg")])
    assert photo is None and not checked


@pytest.mark.asyncio
async def test_without_ai_first_usable_photo(monkeypatch):
    async def dl(url):
        return (None if "dead" in url else (_jpeg(), "image/png"))

    async def ai(name, jpeg):
        return None
    monkeypatch.setattr(photos, "download", dl)
    monkeypatch.setattr(photos, "shows_product", ai)
    photo, checked = await photos.find_photo("X", "https://dead/p.jpg", [_ad(1, "https://x/a.jpg")])
    assert photo.source_url == "https://x/a.jpg" and not checked


def test_llm_image_content_shapes():
    o = llm._openai_content("hi", [(b"\x01\x02", "image/jpeg")])
    assert o[0] == {"type": "text", "text": "hi"} and o[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    a = llm._anthropic_content("hi", [(b"\x01\x02", "image/jpeg")])
    assert a[0]["type"] == "image" and a[0]["source"]["media_type"] == "image/jpeg" and a[-1]["text"] == "hi"
    assert llm._openai_content("hi", None) == "hi" and llm._anthropic_content("hi", None) == "hi"


def test_image_route(monkeypatch):
    from fastapi.testclient import TestClient

    from app import db
    from app.main import app

    async def noop():
        return None

    async def get(pid):
        return (b"JPEGDATA", "image/jpeg") if pid == "22222222-2222-2222-2222-222222222222" else None
    monkeypatch.setattr(db, "connect", noop)
    monkeypatch.setattr(db, "disconnect", noop)
    monkeypatch.setattr(photos, "get", get)
    with TestClient(app) as c:
        assert c.get("/api/v1/images/not-a-uuid.jpg").status_code == 404
        assert c.get("/api/v1/images/33333333-3333-3333-3333-333333333333.jpg").status_code == 404
        r = c.get("/api/v1/images/22222222-2222-2222-2222-222222222222.jpg")
        assert r.status_code == 200 and r.content == b"JPEGDATA"
        assert r.headers["content-type"] == "image/jpeg" and "immutable" in r.headers["cache-control"]


async def test_capture_stores_first_usable_picture_unchecked(monkeypatch):
    saved = []
    urls = {"https://cdn/dead.jpg": None, "https://cdn/ok.jpg": (_jpeg(), "image/jpeg")}

    async def download(url):
        return urls.get(url)

    async def save(pid, photo, checked):
        saved.append((pid, photo.source_url, photo.ad_key, checked))

    monkeypatch.setattr(photos, "download", download)
    monkeypatch.setattr(photos, "save", save)
    ok = await photos.capture("p1", None, [_ad(1, "https://cdn/dead.jpg"), _ad(2, "https://cdn/ok.jpg")])
    assert ok and saved == [("p1", "https://cdn/ok.jpg", "meta:2", False)]
    assert not await photos.capture("p2", None, [_ad(3, "https://cdn/dead.jpg")])


async def test_expired_links_fall_back_to_the_stored_photo(monkeypatch):
    from app import config, db
    ours = f"{config.API_PUBLIC_URL}/images/p1.jpg?v=1"
    executed = []

    async def stored(pid):
        return {"ai_checked": False, "age_days": 2}

    async def get(pid):
        return (_jpeg(), "image/jpeg")

    async def nothing(*a, **k):          # every ad link has expired
        return None

    async def execute(sql, *args):
        executed.append(sql)

    monkeypatch.setattr(photos, "stored", stored)
    monkeypatch.setattr(photos, "get", get)
    monkeypatch.setattr(photos, "download", nothing)
    monkeypatch.setattr(photos, "llm_available", lambda: True)
    monkeypatch.setattr(db, "execute", execute)
    for verdict, expect in ((True, True), (None, True), (False, False)):
        async def shows(name, jpeg, v=verdict):
            return v
        monkeypatch.setattr(photos, "shows_product", shows)
        executed.clear()
        assert await photos.ensure_photo("p1", "Mini Blender", ours, [_ad(1, "https://cdn/dead.jpg")]) is expect
        assert bool(executed) is (verdict is True)      # marked checked only on a yes



async def test_refresh_expired_covers_for_leading_candidates(monkeypatch):
    from app import config
    from app.winners import pipeline, store
    from app.winners.collectors import apify
    v1 = AdRecord(platform="tiktok_organic", external_id="v1", market="US",
                  thumbnail_url="https://p16/old1.jpg", ad_url="https://www.tiktok.com/@a/video/1")
    v2 = AdRecord(platform="tiktok_organic", external_id="v2", market="US",
                  thumbnail_url="https://p16/old2.jpg", ad_url="https://www.tiktok.com/@b/video/2")
    fb = AdRecord(platform="meta", external_id="m1", market="US", thumbnail_url="https://fb/x.jpg")
    results = {"p1": (None, [v1]), "p2": (None, [fb]), "p3": (None, [v2]), "p4": (None, [v2])}
    sent, saved = {}, []

    async def stored(pid):
        return {"ai_checked": True} if pid == "p4" else None     # p4 already has a photo

    async def refresh(urls, market):
        sent["urls"] = urls
        return {"v1": AdRecord(platform="tiktok_organic", external_id="v1", market="US",
                               thumbnail_url="https://p16/fresh1.jpg", ad_url=v1.ad_url)}

    async def upsert(a):
        saved.append(a.external_id)

    monkeypatch.setattr(photos, "stored", stored)
    monkeypatch.setattr(apify, "refresh_tiktok_videos", refresh)
    monkeypatch.setattr(store, "upsert_ad", upsert)
    monkeypatch.setattr(config, "PHOTO_REFRESH_MAX", 20)
    n = await pipeline.refresh_expired_covers("US", ["p1", "p2", "p3", "p4"], results)
    assert sent["urls"] == [v1.ad_url, v2.ad_url]            # TikTok-only candidates without a photo
    assert n == 1 and v1.thumbnail_url == "https://p16/fresh1.jpg" and saved == ["v1"]
    assert v2.thumbnail_url == "https://p16/old2.jpg"        # not returned: unchanged
