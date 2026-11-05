"""TikTok Creative Center Top Ads via Apify."""
from app import config
from app.winners.collectors import apify
from app.winners.markets import get_market

ROW = {"adId": "7300000000000000001", "adTitle": "This mini blender changed my mornings",
       "brandName": "BlendGo", "ctr": 3.1, "likes": 15200, "costScore": 2,
       "objectiveKey": "campaign_objective_product_sales", "coverUrl": "https://p16.tiktokcdn.com/c.jpg",
       "videoUrl720p": "https://v.tiktokcdn.com/v.mp4", "landingPageUrl": "https://blendgo.shop/products/mini",
       "creativeCenterUrl": "https://ads.tiktok.com/business/creativecenter/topads/7300000000000000001/pc/en",
       "durationSec": 21, "rank": 1}


async def test_collects_product_sales_ads_for_the_market(monkeypatch):
    sent = {}

    async def run(actor, payload, timeout=600):
        sent.update(payload, actor=actor)
        return [ROW, dict(ROW, adId="2", objectiveKey="campaign_objective_app_install"), ROW]

    monkeypatch.setattr(apify, "run_actor", run)
    monkeypatch.setattr(config, "APIFY_TIKTOK_ADS_MAX", 60)
    recs = await apify.ApifyTikTokAdsCollector().collect(get_market("UK"))
    assert sent["actor"] == config.APIFY_TIKTOK_ADS_ACTOR and sent["countryCode"] == "GB"
    assert sent["objective"] == "campaign_objective_product_sales" and sent["extractDetails"] is True
    assert sent["maxItems"] == 60
    assert len(recs) == 1                         # app-install ad dropped, duplicate merged
    r = recs[0]
    assert r.platform == "tiktok_ads" and r.advertiser_name == "BlendGo"
    assert r.landing_url == "https://blendgo.shop/products/mini" and r.thumbnail_url.endswith("c.jpg")
    assert abs(r.ctr - 0.031) < 1e-9 and r.likes == 15200


def test_enabled_only_with_an_actor(monkeypatch):
    monkeypatch.setattr(config, "USE_APIFY", True)
    monkeypatch.setattr(config, "APIFY_TOKEN", "t")
    monkeypatch.setattr(config, "APIFY_TIKTOK_ADS_ACTOR", "someone~top-ads")
    assert apify.ApifyTikTokAdsCollector().enabled()
    monkeypatch.setattr(config, "APIFY_TIKTOK_ADS_ACTOR", "")
    assert not apify.ApifyTikTokAdsCollector().enabled()
