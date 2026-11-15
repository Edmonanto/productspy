"""Suggested marketing angles: parsing, freshness, step behaviour."""
import json
from datetime import date

from app.winners import angles
from app.winners.collectors.base import AdRecord

TODAY = date(2026, 10, 28)


def test_parse_keeps_three_to_five_valid_angles():
    ok = lambda n: [{"angle": f"Angle {k}", "hook": f"Hook number {k}", "format": "UGC"} for k in range(n)]
    raw = {"items": [{"i": 0, "angles": ok(6)},                       # capped at 5
                     {"i": 1, "angles": ok(3) + [{"angle": "x"}]},     # invalid one dropped
                     {"i": 7, "angles": ok(3)}, "junk"]}               # index out of range
    out = angles.parse(raw, 2)
    assert len(out[0]) == 5 and len(out[1]) == 3 and 7 not in out


def test_needs_angles_by_market_and_age():
    a = {"angles": [{"angle": "a"}, {"angle": "b"}, {"angle": "c"}], "angles_market": "US", "angles_at": "2026-10-25",
         "avatar": {"name": "x"}}
    assert not angles.needs_angles(a, "US", TODAY)
    assert angles.needs_angles(a, "FR", TODAY)
    assert angles.needs_angles(dict(a, angles_at="2026-10-01"), "US", TODAY)
    assert angles.needs_angles({}, "US", TODAY)
    assert angles.needs_angles(dict(a, angles=[{"angle": "a"}, {"angle": "b"}]), "US", TODAY)  # < 3


def test_prompt_formats_and_skips_template_ads():
    prod = {"title": "Posture Brace", "category": "health", "price_usd": 34.99, "attributes": {"problem": 9}}
    ads = [AdRecord(platform="meta", external_id="1", market="US", ad_text="{{product.name}} | {{product.brand}}"),
           AdRecord(platform="meta", external_id="2", market="US", ad_text="Fix your posture fast")]
    line = json.loads(angles.product_line(0, prod, ads))
    assert line["ad_texts"] == ["Fix your posture fast"]
    angles.PROMPT.format(market="US", language="English", platforms="TikTok", products="x")


async def test_step_writes_only_missing(monkeypatch):
    saved = []
    prods = {"a": ({"title": "A", "category": None, "price_usd": None, "attributes": {}}, []),
             "b": ({"title": "B", "category": None, "price_usd": None,
                    "attributes": {"angles": [{"angle": "x"}] * 3, "angles_market": "US", "angles_at": "2026-10-27",
                                   "avatar": {"name": "x"}}}, [])}

    async def fake(system, prompt, max_tokens=0, purpose=""):
        assert '"product": "A"' in prompt and '"product": "B"' not in prompt
        return {"items": [{"i": 0, "angles": [{"angle": "Demo", "hook": "Watch this", "format": "POV"}]}]}

    async def save(pid, a, m, d, avatar=None):
        saved.append(pid)
    monkeypatch.setattr(angles, "llm_available", lambda: True)
    monkeypatch.setattr(angles, "llm_json", fake)
    monkeypatch.setattr(angles, "save", save)
    stats: dict = {}
    await angles.angles_step("US", ["a", "b"], prods, TODAY, stats)
    assert saved == ["a"] and stats["angles_written"] == 1


def test_avatar_parsed_and_cleaned():
    raw = {"items": [
        {"i": 0, "angles": [], "avatar": {"name": "Busy new mum", "age": "25-34", "gender": "Mostly women",
                                          "situation": "First baby, little sleep", "pains": ["a", "b", "c", "d"],
                                          "wants": ["Calm nights"], "trigger": "Baby won't settle",
                                          "objections": ["Is it safe?"], "platforms": ["tiktok", "Instagram", "MySpace"]}},
        {"i": 1, "avatar": {"age": "30"}},     # no name -> dropped
        {"i": 5, "avatar": {"name": "Out of range"}}]}
    av = angles.parse_avatars(raw, 2)
    assert list(av) == [0]
    assert av[0]["pains"] == ["a", "b", "c"] and av[0]["platforms"] == ["TikTok", "Instagram"]


def test_needs_angles_when_avatar_missing():
    a = {"angles": [{"angle": "a"}] * 3, "angles_market": "US", "angles_at": "2026-10-27"}
    assert angles.needs_angles(a, "US", TODAY)
    assert not angles.needs_angles(dict(a, avatar={"name": "x"}), "US", TODAY)


async def test_step_saves_avatar_in_batches(monkeypatch):
    saved = {}
    prods = {f"p{k}": ({"title": f"P{k}", "category": None, "price_usd": None, "attributes": {}}, []) for k in range(7)}
    calls = []

    async def fake(system, prompt, max_tokens=0, purpose=""):
        n = prompt.count('"product": "P')
        calls.append(n)
        ok = [{"angle": f"A{k}", "hook": f"Hook {k} here", "format": "POV"} for k in range(3)]
        return {"items": [{"i": i, "angles": ok, "avatar": {"name": "Gift buyer"}} for i in range(n)]}

    async def save(pid, a, m, d, avatar=None):
        saved[pid] = avatar
    monkeypatch.setattr(angles, "llm_available", lambda: True)
    monkeypatch.setattr(angles, "llm_json", fake)
    monkeypatch.setattr(angles, "save", save)
    stats: dict = {}
    await angles.angles_step("US", list(prods), prods, TODAY, stats)
    assert calls == [5, 2] and len(saved) == 7 and all(v["name"] == "Gift buyer" for v in saved.values())
    assert stats == {"angles_written": 7, "avatars_written": 7}
