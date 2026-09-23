"""/matches — the review queue for cross-platform matches.

Matching never applies a margin on its own: v1 confidence is capped below the
auto-confirm threshold, so a human decides here. Confirming is the moment a
retail listing stops having an unknown margin and gets an observed one.
"""
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from .. import config, repository, scoring
from ..auth import CurrentUser, current_user

log = logging.getLogger(__name__)

router = APIRouter(prefix="/matches", tags=["matches"])

VALID_STATUSES = ("candidate", "confirmed", "rejected")


def _row_to_match(row) -> dict[str, Any]:
    evidence = row["evidence"]
    if isinstance(evidence, str):
        try:
            evidence = json.loads(evidence)
        except json.JSONDecodeError:
            evidence = {}

    retail_price = float(row["retail_price"]) if row["retail_price"] is not None else None
    supplier_cost = float(row["supplier_cost"]) if row["supplier_cost"] is not None else None

    # Shown as "what you would gain", never written until confirmed.
    projected = None
    if retail_price and supplier_cost and retail_price > 0:
        projected = round((retail_price - supplier_cost) / retail_price * 100)

    return {
        "id": row["id"],
        "confidence": float(row["confidence"]),
        "method": row["method"],
        "status": row["status"],
        "evidence": evidence or {},
        "projected_margin_pct": projected,
        "retail": {
            "id": str(row["retail_id"]),
            "title": row["retail_title"],
            "image_url": row["retail_image"],
            "product_url": row["retail_url"],
            "price_usd": retail_price,
            "source": row["retail_source"],
            "orders_count": row["retail_orders"],
        },
        "supplier": {
            "id": str(row["supplier_id"]),
            "title": row["supplier_title"],
            "title_en": row["supplier_title_en"],
            "image_url": row["supplier_image"],
            "product_url": row["supplier_url"],
            "cost_usd": supplier_cost,
            "source": row["supplier_source"],
        },
    }


@router.get("/")
async def list_matches(
    status_filter: str = Query("candidate", alias="status"),
    limit: int = Query(50, ge=1, le=200),
    user: CurrentUser = Depends(current_user),
) -> dict[str, Any]:
    if status_filter not in VALID_STATUSES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"status must be one of: {', '.join(VALID_STATUSES)}",
        )
    rows = await repository.list_matches(status_filter, limit)
    return {
        "items": [_row_to_match(r) for r in rows],
        "counts": await repository.match_counts(),
    }


@router.post("/{match_id}/confirm")
async def confirm_match(
    match_id: int, user: CurrentUser = Depends(current_user)
) -> dict[str, Any]:
    """Accept a match and give the retail listing the supplier's real cost."""
    row = await repository.get_match(match_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Match not found")
    if row["status"] == "confirmed":
        return {"message": "Already confirmed", "margin_score": None}

    cost = row["supplier_cost"]
    if cost is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Supplier has no cost recorded; nothing to apply.",
        )

    retail_id = str(row["retail_id"])
    await repository.apply_supplier_cost(retail_id, float(cost))
    await repository.set_match_status(match_id, "confirmed")

    # Rescore immediately so the dashboard reflects the real margin without
    # waiting for the next ingestion run.
    product = await repository.get_product(retail_id)
    margin = None
    if product is not None:
        orders = await repository.current_orders(retail_id)
        previous = await repository.orders_at(retail_id, config.TREND_WINDOW_DAYS)
        score = scoring.score_product(
            product, orders_count=orders, previous_orders=previous
        )
        await repository.save_score(retail_id, score)
        margin = score.margin_score

    log.info("match %s confirmed; retail %s now costs %s", match_id, retail_id, cost)
    return {"message": "Match confirmed and margin recomputed", "margin_score": margin}


@router.post("/{match_id}/reject")
async def reject_match(
    match_id: int, user: CurrentUser = Depends(current_user)
) -> dict[str, str]:
    """Reject a match. Sticky — re-running the matcher will not resurrect it."""
    if await repository.get_match(match_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Match not found")
    await repository.set_match_status(match_id, "rejected")
    return {"message": "Match rejected"}
