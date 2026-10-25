"""Daily Winners engine: parsers, enrichment, extraction, scoring — no network, no DB."""
from datetime import datetime, timedelta, timezone

from app.winners.collectors.base import AdRecord, count_intent, to_int, unwrap_redirect, domain_of
from app.winners.collectors.meta_ads import iter_ad_nodes, parse_api_ad, parse_web_ad
from app.winners.collectors.tiktok_ads import iter_materials, parse_material
from app.winners.collectors.tiktok_organic import iter_videos, parse_video
from app.winners.collectors.apify import parse_apify_tiktok
from app.winners.enrich import parse_aliexpress_prices, parse_product_html, parse_shopify_json, to_usd
from app.winners.extract import cluster_keys, heuristic_guess, match_existing, ProductGuess, slugify
from app.winners.scoring import Signals, aggregate, pick_winners, score

NOW = datetime(2026, 10, 24, tzinfo=timezone.utc)


# ---------------------------------------------------------------- helpers

def test_to_int_handles_suffixes():
    assert to_int("1.2M") == 1_200_000
    assert to_int("15K") == 15_000
    assert to_int("1,234") == 1234
    assert to_int("1000+") == 1000
    assert to_int(None) is None


def test_unwrap_facebook_redirect_and_domain():
    u = "https://l.facebook.com/l.php?u=https%3A%2F%2Fshop.example.com%2Fproducts%2Fneck-fan&h=x"
    assert unwrap_redirect(u) == "https://shop.example.com/products/neck-fan"
    assert domain_of("https://www.shop.example.com/x") == "shop.example.com"


def test_intent_comments_multilingual():
    comments = ["where can I buy this??", "link pls", "lol", "c'est combien ?", "so cute", "wo kann ich das kaufen"]
    assert count_intent(comments) == 4


# ---------------------------------------------------------------- parsers

def test_meta_web_parser_walks_nested_graphql():
    blob = {"data": {"ad_library_main": {"search_results_connection": {"edges": [{"node": {"collated_results": [{
        "ad_archive_id": "123", "page_name": "NeckCool", "page_id": "9", "start_date": 1758000000,
        "is_active": True, "collation_count": 4,
        "snapshot": {"body": {"text": "Stay cool all summer"}, "title": "Portable Neck Fan",
                     "link_url": "https://l.facebook.com/l.php?u=https%3A%2F%2Fneckcool.com%2Fproducts%2Fneck-fan",
                     "videos": [{"video_preview_image_url": "https://img/x.jpg", "video_sd_url": "https://v.mp4"}]},
    }]}}]}}}}
    nodes = list(iter_ad_nodes(blob))
    assert len(nodes) == 1
    ad = parse_web_ad(nodes[0], "US")
    assert ad.external_id == "123" and ad.variant_count == 4
    assert ad.landing_url == "https://neckcool.com/products/neck-fan"
    assert ad.landing_domain == "neckcool.com"
    assert ad.thumbnail_url == "https://img/x.jpg"
    assert ad.started_at.year == 2025


def test_meta_api_parser():
    ad = parse_api_ad({
        "id": "55", "page_id": "1", "page_name": "Brand", "ad_delivery_start_time": "2026-09-01",
        "ad_creative_bodies": ["Best posture fix"], "ad_creative_link_titles": ["Posture Corrector"],
        "ad_creative_link_captions": ["POSTUREFIX.COM"], "eu_total_reach": 120000,
    }, "FR")
    assert ad.reach == 120000 and ad.landing_url == "https://posturefix.com" and ad.is_active


def test_tiktok_cc_parser_skips_app_installs():
    payload = {"data": {"materials": [
        {"id": "1", "ad_title": "Neck fan", "brand_name": "Cool", "ctr": 3.2, "like": "12K", "cost": 3,
         "objective_key": "campaign_objective_conversion", "video_info": {"cover": "c.jpg", "video_url": {"720p": "v"}}},
        {"id": "2", "ad_title": "Game", "brand_name": "Game", "ctr": 0.05, "like": 10,
         "objective_key": "campaign_objective_app_install"},
    ]}}
    recs = [r for r in (parse_material(m, "US") for m in iter_materials(payload)) if r]
    assert len(recs) == 1
    assert abs(recs[0].ctr - 0.032) < 1e-9 and recs[0].likes == 12000 and recs[0].budget_level == 3


def test_tiktok_organic_parser():
    blob = {"itemList": [{"id": "77", "desc": "this lamp #tiktokmademebuyit", "createTime": 1761000000,
                          "author": {"uniqueId": "maria", "id": "a1"},
                          "stats": {"playCount": 2_000_000, "diggCount": 150_000, "commentCount": 3000,
                                    "shareCount": 20_000}}]}
    v = [parse_video(x, "US") for x in iter_videos(blob)][0]
    assert v.views == 2_000_000 and v.advertiser_name == "maria"
    assert v.ad_url == "https://www.tiktok.com/@maria/video/77"


def test_apify_tiktok_parser():
    r = parse_apify_tiktok({"id": "9", "text": "x", "playCount": 500000, "diggCount": 1000,
                            "authorMeta": {"name": "bob"}, "webVideoUrl": "https://t/9"}, "AE")
    assert r.views == 500000 and r.market == "AE"


# ---------------------------------------------------------------- enrich

def test_shopify_json_min_variant_price():
    info = parse_shopify_json({"product": {"title": "Fan", "variants": [{"price": "39.99"}, {"price": "29.99"}],
                                           "image": {"src": "i.jpg"}}})
    assert info["price"] == 29.99 and info["image"] == "i.jpg"


def test_jsonld_price():
    html = '<script type="application/ld+json">{"@context":"https://schema.org","@type":"Product","name":"Lamp",' \
           '"image":["a.jpg"],"offers":{"@type":"Offer","price":"34.90","priceCurrency":"EUR"}}</script>'
    info = parse_product_html(html)
    assert info["price"] == 34.9 and info["currency"] == "EUR"
    assert to_usd(34.9, "EUR") == round(34.9 * 1.08, 2)


def test_aliexpress_price_regex():
    html = '"salePrice":{"currency":"USD","minPrice":4.25} ... "minPrice":5.10, "minPrice":999.0'
    assert parse_aliexpress_prices(html) == [4.25, 5.10]


# ---------------------------------------------------------------- extract

def test_heuristic_guess_from_shopify_slug():
    ad = AdRecord(platform="meta", external_id="1", market="US",
                  landing_url="https://x.com/products/new-portable-neck-fan-2026")
    g = heuristic_guess(ad)
    assert g.key == "portable-neck-fan"


def test_clustering_merges_near_duplicates():
    assert match_existing("back-posture-corrector", ["posture-corrector"]) == "posture-corrector"
    assert match_existing("posture-correctors", ["posture-corrector"]) == "posture-corrector"
    assert match_existing("neck-fan", ["posture-corrector"]) is None
    gs = cluster_keys([ProductGuess("sunset-lamp", "Sunset Lamp"), ProductGuess("sunset-lamp-projector", "x"),
                       ProductGuess("lint-remover", "y")], [])
    assert [g.key for g in gs] == ["sunset-lamp", "sunset-lamp", "lint-remover"]


def test_slugify_drops_noise():
    assert slugify("NEW 2026 Best Posture Corrector for Women") == "posture-corrector-women"


# ---------------------------------------------------------------- scoring

def _ads_strong():
    ads = []
    for i in range(10):
        ads.append(AdRecord(platform="meta", external_id=f"m{i}", market="US", advertiser_id=f"s{i % 7}",
                            landing_url=f"https://store{i % 7}.com/products/fan", variant_count=2,
                            started_at=NOW - timedelta(days=3 if i < 4 else 35)))
    ads.append(AdRecord(platform="tiktok_ads", external_id="t1", market="US", ctr=0.035, budget_level=4,
                        likes=40000, shares=6000, started_at=NOW - timedelta(days=5)))
    for i in range(8):
        ads.append(AdRecord(platform="tiktok_organic", external_id=f"o{i}", market="US", advertiser_id=f"c{i}",
                            views=1_500_000, likes=120_000, comments=4_000, shares=18_000,
                            sampled_comments=40, intent_comments=5, started_at=NOW - timedelta(hours=60)))
    return ads


def test_strong_product_is_a_winner():
    sig = aggregate(_ads_strong(), now=NOW, sell_price_usd=34.99, cost_usd=6.0, wow=7, problem=8)
    assert sig.advertisers == 7  # tiktok ad has no store info -> not counted
    assert sig.max_days_running == 35 and sig.new_creatives_7d == 5
    res = score(sig)
    assert res.total >= 80, res
    assert res.confidence == "high"
    assert any("stores selling it" in r for r in res.reasons)
    assert res.excluded is None


def test_weak_single_source_product_scores_low():
    ads = [AdRecord(platform="meta", external_id="x", market="US", advertiser_id="a",
                    started_at=NOW - timedelta(days=2))]
    res = score(aggregate(ads, now=NOW))
    assert res.total < 40
    assert any("one platform" in p["reason"] for p in res.penalties)


def test_missing_data_is_not_zero_but_capped():
    # only organic, very strong — no paid ads at all
    ads = [a for a in _ads_strong() if a.platform == "tiktok_organic"]
    res = score(aggregate(ads, now=NOW, sell_price_usd=30, cost_usd=6))
    assert res.breakdown["scaling"] == 0
    assert 45 <= res.total < 75


def test_saturation_penalty():
    sig = aggregate(_ads_strong(), now=NOW, sell_price_usd=34.99, cost_usd=6.0)
    sig.advertisers = 80
    res = score(sig)
    assert any(p["points"] == 10 for p in res.penalties)


def test_hard_filters():
    base = dict(sell_price_usd=30, cost_usd=5)
    assert score(aggregate(_ads_strong(), now=NOW, restricted=True, **base)).excluded == "restricted category"
    assert score(aggregate(_ads_strong(), now=NOW, ip_risk="high", **base)).excluded == "brand / IP copy risk"
    assert "already picked" in score(aggregate(_ads_strong(), now=NOW, last_picked_days_ago=3, **base)).excluded
    assert score(aggregate(_ads_strong(), now=NOW, last_picked_days_ago=40, **base)).excluded is None


def test_estimated_cost_trusted_less():
    a = score(aggregate(_ads_strong(), now=NOW, sell_price_usd=34.99, cost_usd=6.0))
    b = score(aggregate(_ads_strong(), now=NOW, sell_price_usd=34.99, cost_usd=6.0, cost_estimated=True))
    assert b.breakdown["margin"] < a.breakdown["margin"]


def test_pick_winners_threshold_and_filler():
    from app.winners.scoring import ScoreResult
    mk = lambda t, x=None: ScoreResult(total=t, breakdown={}, excluded=x)
    scored = [("a", mk(91)), ("b", mk(75)), ("c", mk(72, "restricted")), ("d", mk(66)), ("e", mk(64)),
              ("f", mk(62)), ("g", mk(50))]
    picks = pick_winners(scored)
    assert [p[0] for p in picks] == ["a", "b", "d", "e", "f"]
    assert [p[2] for p in picks] == ["winner", "winner", "rising", "rising", "rising"]
    # A thin day: nothing reaches 60, so the best of the rest show as "watch".
    thin = [("x", mk(45)), ("y", mk(31)), ("z", mk(12)), ("r", mk(65))]
    picks = pick_winners(thin)
    assert [(p[0], p[2]) for p in picks] == [("r", "rising"), ("x", "watch"), ("y", "watch")]
    many = [(str(i), mk(70 + i)) for i in range(15)]
    assert len(pick_winners(many)) == 10


def test_unlisted_currency_is_dropped_not_guessed():
    from app.winners.enrich import to_usd
    assert to_usd(100, "JPY") is None
    assert to_usd(100, "AED") == round(100 * 0.272, 2)


def test_every_market_has_terms_and_regions():
    from app.winners.markets import MARKETS
    for m in MARKETS.values():
        assert m.search_terms and m.meta_countries and m.tiktok_regions
    # The official Meta API only covers commercial ads in the EU.
    assert {c for c, m in MARKETS.items() if m.meta_api_ok} == {"EU", "FR", "DE"}


def test_extract_json_tolerates_fences():
    from app.winners.llm import extract_json
    assert extract_json('```json\n[{"i": 0}]\n```') == [{"i": 0}]
    assert extract_json('Here you go: {"a": 1} thanks') == {"a": 1}


async def test_empty_collection_is_reported_not_ok(monkeypatch):
    """Sources that silently return nothing must not produce an 'ok' run."""
    from app.winners import pipeline, store
    from app.winners.collectors.base import Collector

    class Empty(Collector):
        name = "empty"
        def enabled(self): return True
        async def collect(self, market, limit=100): return []

    saved = {}

    async def start_run(_m): return 1
    async def finish_run(_id, status, stats, errors): saved.update(status=status, errors=errors)
    async def unlinked(_m, limit=600): return []
    async def priced(_m, limit=40): return []
    async def products(_m, window_days=60): return {}
    async def picks(_m, _d): return {}
    async def save_winners(*_a): return None

    for name, fn in dict(start_run=start_run, finish_run=finish_run, unlinked_ads=unlinked,
                         products_needing_price=priced, market_products_with_ads=products,
                         last_picks=picks, save_winners=save_winners).items():
        monkeypatch.setattr(store, name, fn)

    res = await pipeline.run_market("US", collectors=[Empty()])
    assert res["status"] == "partial" and saved["status"] == "partial"
    assert "No ads collected" in saved["errors"][0]["error"]


async def test_heuristic_miss_is_retried_not_discarded(monkeypatch):
    """Without the AI, a TikTok video the heuristics can't name must stay
    unlinked (retried later), not be marked 'not a product' forever."""
    from app.winners import extract, pipeline, store

    marked: list = []
    rows = [{"id": "11111111-1111-1111-1111-111111111111"}]
    video = AdRecord(platform="tiktok_organic", external_id="v1", market="US", ad_text="wait for it 😱")

    monkeypatch.setattr(extract, "llm_available", lambda: False)
    async def unlinked(_m, limit=600): return rows
    async def keys(): return []
    async def mark(ids): marked.extend(ids)
    monkeypatch.setattr(store, "unlinked_ads", unlinked)
    monkeypatch.setattr(store, "row_to_ad", lambda _r: video)
    monkeypatch.setattr(store, "existing_keys", keys)
    monkeypatch.setattr(store, "mark_not_product", mark)

    stats: dict = {}
    await pipeline.extract_step("US", stats)
    assert marked == [] and stats["unidentified_ads"] == 1 and stats["linked_ads"] == 0
