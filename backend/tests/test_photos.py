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


# ── store pages and extra ad pictures (when no ad picture shows the product) ──

def test_candidates_include_every_ad_picture_after_thumbnails():
    a = _ad(1, "https://x/thumb.jpg")
    a.raw = {"images": ["https://x/card2.jpg", "https://x/thumb.jpg", "https://x/card3.jpg"]}
    b = _ad(2, "https://x/b.jpg")
    urls = [u for u, _ in photos.candidates(None, [a, b])]
    assert urls == ["https://x/thumb.jpg", "https://x/b.jpg", "https://x/card2.jpg", "https://x/card3.jpg"]


def test_store_pages_one_per_site_products_first_no_social():
    ads = [AdRecord(platform="meta", external_id="1", market="US", landing_url="https://shop.com/collections/all"),
           AdRecord(platform="meta", external_id="2", market="US", landing_url="https://other.com/products/brace"),
           AdRecord(platform="meta", external_id="3", market="US", landing_url="https://www.facebook.com/somepage"),
           AdRecord(platform="meta", external_id="4", market="US", landing_url="https://shop.com/products/brace")]
    assert photos.store_pages("https://www.facebook.com/ads/library/?id=9", ads) == \
        ["https://other.com/products/brace", "https://shop.com/products/brace"]


def test_page_images_jsonld_then_og():
    html = """<html><head>
      <meta content="//cdn.shop.com/og.jpg" property="og:image">
      <script type="application/ld+json">{"@context":"https://schema.org","@graph":[
        {"@type":"Product","name":"Brace","image":["/files/a.jpg",{"url":"https://cdn.shop.com/b.jpg"}]}]}</script>
      <meta name="twitter:image" content="https://cdn.shop.com/a.jpg?x=1&amp;y=2"></head></html>"""
    assert photos.page_images(html, "https://shop.com/products/brace") == [
        "https://shop.com/files/a.jpg", "https://cdn.shop.com/b.jpg",
        "https://cdn.shop.com/og.jpg", "https://cdn.shop.com/a.jpg?x=1&y=2"]


def test_shopify_images():
    data = {"product": {"image": {"src": "//cdn.shopify.com/1.jpg"},
                        "images": [{"src": "//cdn.shopify.com/1.jpg"}, {"src": "https://cdn.shopify.com/2.jpg"}]}}
    assert photos.shopify_images(data) == ["https://cdn.shopify.com/1.jpg", "https://cdn.shopify.com/2.jpg"]
    assert photos.shopify_images({"nope": 1}) == []


@pytest.mark.asyncio
async def test_store_page_photo_used_when_ads_show_something_else(monkeypatch):
    ads = [AdRecord(platform="meta", external_id="1", market="US", thumbnail_url="https://x/person.jpg",
                    landing_url="https://shop.com/products/brace")]

    async def dl(url):
        return _jpeg(), "image/png"

    async def ai(name, jpeg):
        return ai.calls.pop(0)
    ai.calls = [False, True]                    # ad picture: no; store photo: yes
    fetched = []

    async def fetch(url, timeout=10.0):
        fetched.append(url)
        return url, '{"product": {"images": [{"src": "https://cdn.shop.com/brace.jpg"}]}}'
    monkeypatch.setattr(photos, "download", dl)
    monkeypatch.setattr(photos, "shows_product", ai)
    monkeypatch.setattr(photos, "fetch_text", fetch)
    photo, checked = await photos.find_photo("Posture Brace", None, ads)
    assert checked and photo.source_url == "https://cdn.shop.com/brace.jpg" and photo.ad_key is None
    assert fetched == ["https://shop.com/products/brace.json"]


@pytest.mark.asyncio
async def test_store_pages_not_opened_when_an_ad_picture_matches(monkeypatch):
    ads = [AdRecord(platform="meta", external_id="1", market="US", thumbnail_url="https://x/ok.jpg",
                    landing_url="https://shop.com/products/brace")]

    async def dl(url):
        return _jpeg(), "image/png"

    async def ai(name, jpeg):
        return True

    async def fetch(url, timeout=10.0):
        raise AssertionError("store page should not be fetched")
    monkeypatch.setattr(photos, "download", dl)
    monkeypatch.setattr(photos, "shows_product", ai)
    monkeypatch.setattr(photos, "fetch_text", fetch)
    photo, checked = await photos.find_photo("Posture Brace", None, ads)
    assert checked and photo.source_url == "https://x/ok.jpg"


def test_meta_ad_keeps_every_picture():
    from app.winners.collectors.meta_ads import ad_images
    snap = {"images": [{"original_image_url": "https://x/1.jpg"}, {"resized_image_url": "https://x/2.jpg"}]}
    cards = [{"original_image_url": "https://x/3.jpg"}, {"video_preview_image_url": "https://x/1.jpg"}, "junk"]
    assert ad_images(snap, cards, "https://x/1.jpg") == ["https://x/2.jpg", "https://x/3.jpg"]


@pytest.mark.asyncio
async def test_checked_photo_kept_when_image_url_was_replaced_by_an_ad_link(monkeypatch):
    from app import db
    executed = []

    async def stored(pid):
        return {"ai_checked": True, "age_days": 3}

    async def execute(sql, *args):
        executed.append(args)

    async def never(*a, **k):
        raise AssertionError("no new photo search needed")
    monkeypatch.setattr(photos, "stored", stored)
    monkeypatch.setattr(photos, "find_photo", never)
    monkeypatch.setattr(db, "execute", execute)
    assert await photos.ensure_photo("p1", "Charger", "https://p19.tiktokcdn.com/fresh.jpg", []) is True
    assert executed and executed[0][1].startswith(f"{photos.config.API_PUBLIC_URL}/images/p1.jpg")


@pytest.mark.asyncio
async def test_stored_photo_used_when_fresh_ad_link_is_rejected(monkeypatch):
    from app import db
    executed = []

    async def stored(pid):
        return {"ai_checked": False, "age_days": 3}

    async def dl(url):
        return _jpeg(), "image/png"

    async def get(pid):
        return (b"stored", "image/jpeg")

    async def shows(name, jpeg):
        return jpeg == b"stored"             # the ad link: no; our stored photo: yes

    async def execute(sql, *args):
        executed.append(sql)
    monkeypatch.setattr(photos, "stored", stored)
    monkeypatch.setattr(photos, "download", dl)
    monkeypatch.setattr(photos, "get", get)
    monkeypatch.setattr(photos, "shows_product", shows)
    monkeypatch.setattr(photos, "llm_available", lambda: True)
    monkeypatch.setattr(db, "execute", execute)
    assert await photos.ensure_photo("p1", "Charger", "https://p19.tiktokcdn.com/fresh.jpg", []) is True
    assert any("ai_checked = true" in q for q in executed) and any("set image_url" in q for q in executed)


@pytest.mark.asyncio
async def test_refresh_covers_when_stored_photo_unchecked_up_to_three_videos(monkeypatch):
    from app import config
    from app.winners import pipeline
    from app.winners.collectors import apify
    vids = [AdRecord(platform="tiktok_organic", external_id=f"v{k}", market="US", views=k * 10,
                     ad_url=f"https://www.tiktok.com/@a/video/{k}") for k in range(5)]
    sent = {}

    async def stored(pid):
        return {"ai_checked": False}         # captured at collection, never confirmed

    async def refresh(urls, market):
        sent["urls"] = urls
        return {}
    monkeypatch.setattr(photos, "stored", stored)
    monkeypatch.setattr(apify, "refresh_tiktok_videos", refresh)
    monkeypatch.setattr(config, "PHOTO_REFRESH_MAX", 20)
    await pipeline.refresh_expired_covers("US", ["p1"], {"p1": (None, vids)})
    assert sent["urls"] == [vids[4].ad_url, vids[3].ad_url, vids[2].ad_url]   # most viewed first
