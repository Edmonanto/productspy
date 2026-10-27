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


AI_ATTRS = dict(wow=7, problem=8, demo3s=True, upsell=6, brandable=7, ip_risk="none",
                fragile_heavy=False, seasonal=False)


def test_strong_product_is_a_winner():
    sig = aggregate(_ads_strong(), now=NOW, sell_price_usd=34.99, cost_usd=6.0, **AI_ATTRS)
    assert sig.advertisers == 7  # tiktok ad has no store info -> not counted
    assert sig.max_days_running == 35 and sig.new_creatives_7d == 5
    res = score(sig)
    assert res.total >= 80, res
    assert res.confidence == "high"
    assert set(res.breakdown) == {"demand", "profitability", "competition", "creative",
                                  "differentiation", "logistics", "market_fit", "risk"}
    assert all(v is not None for v in res.breakdown.values())
    assert any("stores running ads" in r for r in res.reasons)
    assert res.excluded is None
    assert pick_winners([("p", res)])[0][2] == "winner"


def test_every_criterion_has_tagged_evidence():
    res = score(aggregate(_ads_strong(), now=NOW, sell_price_usd=34.99, cost_usd=6.0, **AI_ATTRS))
    crit = res.signals["criteria"]
    for k, info in crit.items():
        assert info["known"] and info["evidence"], k
        assert all(e["kind"] in {"observed", "calculated", "ai", "assumption"} for e in info["evidence"])
    kinds = {e["kind"] for e in crit["profitability"]["evidence"]}
    assert {"calculated", "assumption"} <= kinds
    # views are never presented as sales
    demand_text = " ".join(e["text"] for e in crit["demand"]["evidence"])
    assert "views are not sales" in demand_text


def test_weights_sum_to_100_and_can_be_overridden():
    from app.winners.scoring import CRITERIA, load_weights
    assert abs(sum(CRITERIA.values()) - 100) < 1e-6 and CRITERIA["demand"] == 20 and CRITERIA["risk"] == 5
    w = load_weights('{"demand": 40, "risk": 0}')
    assert abs(sum(w.values()) - 100) < 1e-6 and w["risk"] == 0 and w["demand"] > 20
    assert load_weights("not json") == load_weights("")


def test_weak_single_source_product_scores_low():
    ads = [AdRecord(platform="meta", external_id="x", market="US", advertiser_id="a",
                    started_at=NOW - timedelta(days=2))]
    res = score(aggregate(ads, now=NOW))
    assert res.total < 55
    assert res.confidence == "low"
    assert pick_winners([("p", res)]) == [] or pick_winners([("p", res)])[0][2] == "watch"


def test_missing_criterion_is_left_out_not_zero():
    # only organic, very strong — no paid ads at all
    ads = [a for a in _ads_strong() if a.platform == "tiktok_organic"]
    res = score(aggregate(ads, now=NOW, sell_price_usd=30, cost_usd=6, **AI_ATTRS))
    assert res.breakdown["competition"] is None          # no stores seen advertising
    assert "competition" in res.signals["missing_pillars"]
    assert not res.signals["criteria"]["competition"]["known"]
    assert res.total <= 85                                 # one platform: capped
    assert res.confidence in ("low", "medium")


def test_facebook_only_long_runner_is_not_buried():
    ads = [AdRecord(platform="meta", external_id=f"f{i}", market="US", advertiser_id=f"s{i % 3}",
                    landing_url=f"https://shop{i % 3}.com/products/x", variant_count=3,
                    started_at=NOW - timedelta(days=229 if i == 0 else 120)) for i in range(4)]
    res = score(aggregate(ads, now=NOW))
    assert res.breakdown["profitability"] is None and res.breakdown["creative"] is None
    assert 55 <= res.total <= 85, res
    assert res.confidence == "low"
    assert pick_winners([("p", res)])[0][2] == "rising"   # low confidence can't be "winner"


def test_single_strong_signal_cannot_score_high():
    ads = [AdRecord(platform="meta", external_id=f"z{i}", market="US", advertiser_id="one",
                    variant_count=5, started_at=NOW - timedelta(days=60)) for i in range(4)]
    res = score(aggregate(ads, now=NOW))
    assert res.total <= 75


def test_competition_is_not_punished_per_se_but_saturation_is():
    base = dict(sell_price_usd=34.99, cost_usd=6.0, **AI_ATTRS)
    ok = score(aggregate(_ads_strong(), now=NOW, **base))
    sig = aggregate(_ads_strong(), now=NOW, **base)
    sig.advertisers = 80
    sat = score(sig)
    assert sat.breakdown["competition"] < ok.breakdown["competition"]
    assert any("saturated" in e["text"] for e in sat.signals["criteria"]["competition"]["evidence"])
    assert ok.breakdown["competition"] == ok.signals["criteria"]["competition"]["max"]


def test_hard_filters():
    base = dict(sell_price_usd=30, cost_usd=5)
    assert score(aggregate(_ads_strong(), now=NOW, restricted=True, **base)).excluded == "restricted category"
    assert score(aggregate(_ads_strong(), now=NOW, ip_risk="high", **base)).excluded == "brand / IP copy risk"
    assert "already picked" in score(aggregate(_ads_strong(), now=NOW, last_picked_days_ago=3, **base)).excluded
    assert score(aggregate(_ads_strong(), now=NOW, last_picked_days_ago=40, **base)).excluded is None


def test_estimated_cost_trusted_less():
    a = score(aggregate(_ads_strong(), now=NOW, sell_price_usd=34.99, cost_usd=6.0))
    b = score(aggregate(_ads_strong(), now=NOW, sell_price_usd=34.99, cost_usd=6.0, cost_estimated=True))
    assert b.breakdown["profitability"] < a.breakdown["profitability"]
    assert any(e["kind"] == "ai" for e in b.signals["criteria"]["profitability"]["evidence"])


def test_trend_status_from_time_series():
    from app.winners.scoring import trend_status
    ads = [AdRecord(platform="meta", external_id=f"t{i}", market="US", advertiser_id=f"s{i}",
                    started_at=NOW - timedelta(days=90)) for i in range(2)]
    falling = aggregate(ads, now=NOW, paid_ads_history=[8, 9, 8, 2])
    assert trend_status(falling)[0] == "declining"
    rising = aggregate(ads * 3, now=NOW, paid_ads_history=[1, 2, 2, 6])
    assert trend_status(rising)[0] == "growing"
    assert trend_status(aggregate([], now=NOW))[0] == "unknown"
    assert trend_status(aggregate([], now=NOW, seasonal=True))[0] == "seasonal"
    res = score(falling)
    assert res.signals["trend"] == "declining"


def test_band_labels():
    from app.winners.scoring import band
    assert band(90).startswith("Exceptional") and band(72).startswith("Strong")
    assert band(60).startswith("Promising") and band(45).startswith("Weak") and band(10).startswith("Low")


def test_pick_winners_threshold_and_filler():
    from app.winners.scoring import ScoreResult
    mk = lambda t, x=None, c="medium": ScoreResult(total=t, breakdown={}, excluded=x, confidence=c)
    scored = [("a", mk(91)), ("b", mk(75)), ("c", mk(72, "restricted")), ("d", mk(66)), ("e", mk(64)),
              ("f", mk(58)), ("g", mk(50))]
    picks = pick_winners(scored)
    assert [p[0] for p in picks] == ["a", "b", "d", "e", "f"]
    assert [p[2] for p in picks] == ["winner", "winner", "rising", "rising", "rising"]
    # A thin day: few reach 55, so the best of the rest (40+) show as "watch".
    thin = [("x", mk(45)), ("y", mk(41)), ("z", mk(32)), ("r", mk(65))]
    picks = pick_winners(thin)
    assert [(p[0], p[2]) for p in picks] == [("r", "rising"), ("x", "watch"), ("y", "watch")]
    assert pick_winners([("lo", mk(78, c="low"))])[0][2] == "rising"
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


async def test_openai_used_when_no_anthropic_key(monkeypatch):
    from app import config
    from app.winners import llm

    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(config, "OPENAI_API_KEY", "sk-test")
    assert llm.provider() == "openai" and llm.llm_available()

    seen = {}

    class Resp:
        status_code = 200
        text = ""
        def json(self):
            return {"choices": [{"message": {"content": '```json\n[{"i": 0, "product": "Posture corrector"}]\n```'}}]}

    class Client:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, headers=None, json=None):
            seen.update(url=url, auth=headers["Authorization"], model=json["model"])
            return Resp()

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", Client)
    out = await llm.llm_json("sys", "prompt")
    assert out == [{"i": 0, "product": "Posture corrector"}]
    assert seen["url"].endswith("/chat/completions") and seen["auth"] == "Bearer sk-test"

    monkeypatch.setattr(config, "OPENAI_API_KEY", "")
    assert llm.provider() is None


async def test_verify_keeps_only_ads_that_show_the_product(monkeypatch):
    from app.winners import verify

    ads = [AdRecord(platform="meta", external_id=str(i), market="US", ad_text=t, thumbnail_url=f"img{i}")
           for i, t in enumerate(["Posture corrector, fix your back", "Summer sale on everything",
                                  "This posture brace changed my life"])]

    async def fake_llm(system, prompt, max_tokens=8000):
        assert "Posture Corrector" in prompt
        return {"matches": [0, 2], "best": 2, "name": "posture corrector brace"}

    monkeypatch.setattr(verify, "llm_available", lambda: True)
    monkeypatch.setattr(verify, "llm_json", fake_llm)
    v = await verify.verify_product("Posture Corrector", ads, already_ok=set())
    assert v.checked and [a.external_id for a in v.keep] == ["0", "2"]
    assert [a.external_id for a in v.reject] == ["1"]
    assert v.best.thumbnail_url == "img2" and v.name == "Posture Corrector Brace"

    # already-verified ads are not sent again; nothing new -> no call, nothing changes
    called = False
    async def never(*a, **k):
        nonlocal called; called = True
    monkeypatch.setattr(verify, "llm_json", never)
    v2 = await verify.verify_product("Posture Corrector", ads, already_ok={"meta:0", "meta:1", "meta:2"})
    assert not called and not v2.checked and len(v2.keep) == 3


async def test_verify_without_ai_changes_nothing(monkeypatch):
    from app.winners import verify
    monkeypatch.setattr(verify, "llm_available", lambda: False)
    ads = [AdRecord(platform="meta", external_id="1", market="US", ad_text="x")]
    v = await verify.verify_product("Thing", ads, set())
    assert not v.checked and v.keep == ads and not v.reject


async def test_verify_step_drops_product_whose_ads_dont_match(monkeypatch):
    from datetime import date, datetime, timezone
    from app.winners import pipeline, store, verify

    good = [AdRecord(platform="meta", external_id="g", market="US", ad_text="LED mirror",
                     started_at=NOW - timedelta(days=20), variant_count=6)]
    bad = [AdRecord(platform="meta", external_id="b", market="US", ad_text="Huge sale",
                    started_at=NOW - timedelta(days=30), variant_count=9)]
    prod = lambda t: {"title": t, "attributes": {"physical": True}, "price_usd": None,
                      "cost_usd": None, "cost_estimated": False}
    products = {"p1": (prod("Led Mirror"), good), "p2": (prod("Sale"), bad)}
    day, now = date(2026, 10, 25), NOW
    results = {pid: (pipeline.score(pipeline._signals(p, a, day, now, None)), a) for pid, (p, a) in products.items()}

    async def fake_verify(name, ads, ok):
        if name == "Sale":
            return verify.Verdict(reject=list(ads), checked=True)
        return verify.Verdict(keep=list(ads), best=ads[0], checked=True)
    rejected, marked = [], []
    async def rej(m, pid, ads): rejected.append((pid, [a.external_id for a in ads]))
    async def mark(pid, keys, img, name): marked.append((pid, keys))
    monkeypatch.setattr(pipeline, "verify_product", fake_verify)
    monkeypatch.setattr(store, "reject_ads", rej)
    monkeypatch.setattr(store, "mark_verified", mark)

    stats: dict = {}
    await pipeline.verify_step("US", products, results, stats, day, now, {})
    assert rejected == [("p2", ["b"])] and stats["ads_rejected"] == 1
    assert results["p2"][0].excluded == "its ads don't show this product"
    assert results["p1"][0].excluded is None and ("p1", ["meta:g"]) in marked


async def test_verify_flags_a_non_product(monkeypatch):
    from app.winners import verify
    ads = [AdRecord(platform="meta", external_id="1", market="US", ad_text="Learn dropshipping in 30 days")]

    async def fake_llm(system, prompt, max_tokens=8000):
        return {"is_product": False, "matches": [], "best": None, "name": None}
    monkeypatch.setattr(verify, "llm_available", lambda: True)
    monkeypatch.setattr(verify, "llm_json", fake_llm)
    v = await verify.verify_product("Dropshipping Course", ads, set())
    assert v.not_product and not v.keep


async def test_verify_step_excludes_non_products(monkeypatch):
    from datetime import date
    from app.winners import pipeline, store, verify
    ads = [AdRecord(platform="meta", external_id="c", market="US", ad_text="Join my course",
                    started_at=NOW - timedelta(days=40), variant_count=8)]
    prod = {"title": "Wellness Starter Pack", "attributes": {"physical": True}, "price_usd": None,
            "cost_usd": None, "cost_estimated": False}
    products = {"p": (prod, ads)}
    day = date(2026, 10, 25)
    results = {"p": (pipeline.score(pipeline._signals(prod, ads, day, NOW, None)), ads)}

    async def fake_verify(name, ads, ok):
        return verify.Verdict(reject=list(ads), checked=True, not_product=True)
    calls = []
    async def rej(m, pid, a): calls.append(("reject", pid))
    async def phys(pid): calls.append(("not_physical", pid))
    monkeypatch.setattr(pipeline, "verify_product", fake_verify)
    monkeypatch.setattr(store, "reject_ads", rej)
    monkeypatch.setattr(store, "mark_not_physical", phys)
    stats: dict = {}
    verified = await pipeline.verify_step("US", products, results, stats, day, NOW, {})
    assert results["p"][0].excluded == "not a physical product"
    assert ("not_physical", "p") in calls and stats["not_products_dropped"] == 1
    assert "p" not in verified


async def test_with_ai_key_no_guesswork_products(monkeypatch):
    from app.winners import extract
    ads = [AdRecord(platform="meta", external_id="1", market="US",
                    ad_text="Spring Collection | Shop now", landing_url="https://x.com/products/spring-collection")]

    async def failed_ai(ads, batch=40):
        return {}            # AI batch failed / didn't answer
    monkeypatch.setattr(extract, "llm_available", lambda: True)
    monkeypatch.setattr(extract, "ai_guesses", failed_ai)
    out = await extract.guess_products_detailed(ads)
    assert out == [(None, False)]     # left for the next run, not turned into a product


def test_price_without_cost_is_not_scored_as_profitable():
    ads = [AdRecord(platform="meta", external_id=f"q{i}", market="US", advertiser_id=f"s{i % 3}",
                    started_at=NOW - timedelta(days=30)) for i in range(4)]
    res = score(aggregate(ads, now=NOW, sell_price_usd=24.99))
    assert res.breakdown["profitability"] is None
    assert "no product cost" in res.signals["criteria"]["profitability"]["evidence"][0]["text"]


def test_risk_evidence_not_labelled_ai_when_ai_never_looked():
    ads = [AdRecord(platform="meta", external_id=f"r{i}", market="US", advertiser_id="s",
                    started_at=NOW - timedelta(days=40)) for i in range(3)]
    ev = score(aggregate(ads, now=NOW)).signals["criteria"]["risk"]["evidence"]
    assert ev and all(e["kind"] != "ai" for e in ev)


def test_all_prompts_format_without_errors():
    from app.winners import cleanup, extract, verify
    assert '{"items"' in extract.PROMPT.format(ads="x")
    verify.PROMPT.format(name="n", ads="a")
    cleanup.PROMPT.format(items="i")


def test_apps_and_media_are_never_products():
    from app.winners.filters import non_product_advertiser, non_product_reason
    for bad in ["Canva Design App", "AI Drama Short Series", "Short Drama Episodes", "Meal Kit Subscription",
                "Photo Editor App", "Online Fitness Course", "ReelShort", "Gut Health Supplement"]:
        assert non_product_reason(bad), bad
    for good in ["Posture Corrector Brace", "Power Bank 20000mAh", "Travel Neck Pillow", "Hair Extension Clip",
                 "Streaming Microphone USB", "Game Controller Grip", "App Controlled LED Strip Light",
                 "Kindle Case Cover", "Card Game For Families"]:
        assert non_product_reason(good) is None, good
    assert non_product_advertiser("Canva") and non_product_advertiser("DramaBox Official")
    assert not non_product_advertiser("BackFix Store")
    res = score(aggregate(_ads_strong(), now=NOW, physical=False))
    assert res.excluded == "not a physical product"


async def test_shown_picks_skip_non_products_and_imageless(monkeypatch):
    from datetime import date
    from app import db as dbm
    from app.winners import store
    rows = [{"rank": 1, "title": "Canva Pro App", "category": "other", "image_url": "https://x/i.jpg"},
            {"rank": 2, "title": "Posture Brace", "category": "health", "image_url": None},
            {"rank": 3, "title": "LED Projector", "category": "home", "image_url": "https://x/p.jpg"}]

    async def fetch(*a, **k):
        return rows
    monkeypatch.setattr(dbm, "fetch", fetch)
    out = await store.picks("US", date.today())
    assert [(r["rank"], r["title"]) for r in out] == [(1, "LED Projector")]
