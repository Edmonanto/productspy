"""Public landing-page preview: #1 in full, the rest without names, prices or links."""
import json
from datetime import date

from app.routers.winners import preview_payload


def _row(rank: int) -> dict:
    return {
        "rank": rank, "total": 90 - rank, "tier": "winner", "category": "home",
        "image_url": f"https://img/{rank}.jpg", "title": f"Secret product {rank}",
        "price_usd": 29.9, "breakdown": json.dumps({"demand": 15}),
        "signals": json.dumps({"trend": "growing", "advertisers": 7, "max_days_running": 21}),
        "attributes": json.dumps({"angles": [{"angle": "Problem/solution", "hook": "Stop doing this"}]}),
        "store_url": "https://store", "ad_url": "https://ad", "supplier_url": "https://supplier",
    }


def test_preview_reveals_only_first_pick():
    data = preview_payload("US", date(2026, 10, 29), [_row(i) for i in range(1, 9)])
    assert data["total"] == 8 and len(data["picks"]) == 6
    first, second = data["picks"][0], data["picks"][1]
    assert first["revealed"] and first["title"] == "Secret product 1" and first["angle"]["hook"] == "Stop doing this"
    assert not second["revealed"]
    hidden = json.dumps(data["picks"][1:])
    for leak in ("Secret product", "price_usd", "store", "https://ad", "supplier", "hook"):
        assert leak not in hidden


def test_preview_empty_market():
    data = preview_payload("US", None, [])
    assert data["date"] is None and data["picks"] == []
