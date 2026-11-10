"""Daily video brief: why each pick won + a short-video script."""
import json
from datetime import date

import pytest

from app import config, owner_notify
from app.winners import video_brief

DAY = date(2026, 11, 11)


def _row(market="US", rank=1, title="Magnetic Cable Organizer"):
    return {
        "rank": rank, "tier": "rising", "total": 72, "product_id": f"00000000-0000-0000-0000-00000000000{rank}",
        "pick_date": DAY, "market": market,
        "breakdown": json.dumps({"demand": 14.2, "profitability": None}), "reasons": "[]", "penalties": "[]",
        "confidence": "medium",
        "signals": json.dumps({"band": "Strong candidate worth validating", "trend": "growing",
                               "trend_why": "3 of 5 active ads launched in the last 14 days",
                               "strengths": ["4 different stores running ads for it"],
                               "weaknesses": ["Product cost is an AI estimate"], "advertisers": 4,
                               "max_days_running": 21, "creatives": 9, "videos": 2, "total_views": 1200000,
                               "meta_ads": 5, "still_winning": True}),
        "title": title, "image_url": "https://img.example/x.jpg", "category": "home", "price_usd": 24.99,
        "cost_usd": 4.0, "cost_estimated": True, "product_url": None,
        "attributes": json.dumps({"angles": [{"hook": "Cables everywhere?"}]}),
        "supplier_url": None, "ad_url": "https://facebook.com/ads/library/?id=1", "store_url": "https://shop.example",
    }


SCRIPT = {"i": 0, "title": "This $25 organizer is everywhere", "hook": "4 stores are paying to sell this",
          "length_seconds": 30, "format": "screen recording + product shots",
          "scenes": [{"time": "0-3s", "visual": "Product photo", "on_screen": "Winning now", "voiceover": "Look"},
                     {"time": "3-10s", "visual": "Dashboard score 72", "on_screen": "72/100", "voiceover": "Score"},
                     {"time": "25-30s", "visual": "productspy.pro", "on_screen": "Link in bio", "voiceover": "Go"}],
          "cta": "See today's list at productspy.pro", "caption": "Winning product of the day",
          "hashtags": ["#dropshipping", "#winningproducts"], "filming_tips": ["Film vertical"]}


def test_parse_keeps_valid_scripts_only():
    bad = {"i": 1, "title": "x", "hook": "y", "scenes": [], "cta": "z"}   # too few scenes
    out = video_brief.parse({"items": [SCRIPT, bad, {"i": 9}]}, 2)
    assert list(out) == [0] and out[0]["hook"].startswith("4 stores")


@pytest.mark.asyncio
async def test_send_daily_builds_full_email(monkeypatch):
    sent = []

    async def latest(market, day):
        return DAY if market in ("US", "FR") else None

    async def picks(market, day):
        return [_row(market, 1), _row(market, 2, "Mini Blender"), _row(market, 3, "Third")]

    async def fake_llm(system, prompt, max_tokens=0, purpose=""):
        assert "French" in prompt if "France" in prompt else "English" in prompt
        return {"items": [SCRIPT]}

    async def fake_send(subject, body, reply_to=None):
        sent.append((subject, body))
        return 1

    monkeypatch.setattr(config, "VIDEO_BRIEF_MARKETS", ["US", "UK", "FR"])
    monkeypatch.setattr(config, "VIDEO_BRIEF_PER_MARKET", 2)
    monkeypatch.setattr(video_brief.store, "latest_pick_date", latest)
    monkeypatch.setattr(video_brief.store, "picks", picks)
    monkeypatch.setattr(video_brief, "llm_available", lambda: True)
    monkeypatch.setattr(video_brief, "llm_json", fake_llm)
    monkeypatch.setattr(owner_notify, "send", fake_send)

    assert await video_brief.send_daily(DAY) == 1
    subject, body = sent[0]
    assert subject.startswith("🎬 Video ideas 2026-11-11")
    assert body.count("Why it was picked") == 4            # 2 markets × 2 picks, UK had no picks today
    assert "Third" not in body
    assert "4 different stores running ads for it" in body and "Product cost is an AI estimate" in body
    assert "$24.99" in body and "1,200,000" in body and "still winning" in body
    assert "4 stores are paying to sell this" in body       # script hook
    assert "No script today" in body                        # 2nd pick had no script in the fake reply


@pytest.mark.asyncio
async def test_no_ai_still_sends_details(monkeypatch):
    async def latest(market, day):
        return DAY

    async def picks(market, day):
        return [_row(market)]

    sent = []

    async def fake_send(subject, body, reply_to=None):
        sent.append(body)
        return 1

    monkeypatch.setattr(config, "VIDEO_BRIEF_MARKETS", ["US"])
    monkeypatch.setattr(video_brief.store, "latest_pick_date", latest)
    monkeypatch.setattr(video_brief.store, "picks", picks)
    monkeypatch.setattr(video_brief, "llm_available", lambda: False)
    monkeypatch.setattr(owner_notify, "send", fake_send)
    assert await video_brief.send_daily(DAY) == 1
    assert "Why it was picked" in sent[0] and "No script today" in sent[0]
