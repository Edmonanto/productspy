"""AI product naming: small batches, and skipped ads are asked again."""
from app.winners import extract
from app.winners.collectors.base import AdRecord


def _ads(n):
    return [AdRecord(platform="meta", external_id=str(i), market="US", ad_text=f"Ad {i}") for i in range(n)]


import re

WORDS = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel", "india", "juliet"]


def _name(i):
    return f"{WORDS[i // 10]} {WORDS[i % 10]}"


def _row(i):
    return {"i": i, "product": f"Gadget {_name(i)}", "key": f"gadget {_name(i)}", "category": "home"}


async def test_lost_batch_is_retried_in_smaller_batches(monkeypatch):
    calls = []

    async def fake_llm(system, prompt, *a, **k):
        idxs = [int(m) for m in re.findall(r'^\{"i": (\d+),', prompt, re.M)]
        calls.append(len(idxs))
        if len(calls) == 1:
            return "garbled"                  # first batch's reply is lost
        if len(calls) == 2:
            return [_row(i) for i in idxs[:-3]]   # second batch skips its last 3 ads
        return [_row(i) for i in idxs]

    monkeypatch.setattr(extract, "llm_json", fake_llm)
    out = await extract.ai_guesses(_ads(30))
    assert sorted(out) == list(range(30))
    assert all(out[i].name == f"Gadget {_name(i)}".title() for i in range(30))
    assert calls[:2] == [20, 10] and max(calls[2:]) <= 8


async def test_not_a_product_and_bad_indexes(monkeypatch):
    async def fake_llm(system, prompt, *a, **k):
        return [{"i": 0, "product": None}, {"i": "x"}, {"i": 99, "product": "Nope"}, _row(1)]

    monkeypatch.setattr(extract, "llm_json", fake_llm)
    out = await extract.ai_guesses(_ads(2))
    assert out[0] is None and out[1].name == "Gadget Alpha Bravo" and 99 not in out
