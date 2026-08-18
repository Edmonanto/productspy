"""/billing — subscription status now; provider integration in Phase 3.

`GET /billing/status` is fully implemented and reads real subscription rows.
Checkout, portal and cancel require Stripe/PayPal credentials and webhook
handling, so they return 501 rather than pretending to succeed — the frontend
surfaces the `detail` message to the user.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status

from .. import quota, repository
from ..auth import CurrentUser, current_user
from ..schemas import BillingStatus

router = APIRouter(prefix="/billing", tags=["billing"])

_NOT_IMPLEMENTED = "Billing is not yet enabled. Payment provider integration is pending."


@router.get("/status", response_model=BillingStatus)
async def get_status(user: CurrentUser = Depends(current_user)) -> BillingStatus:
    subscription, provider = await repository.subscription(user.id)
    return BillingStatus(
        plan=subscription.plan,
        status=subscription.status,
        provider=provider,
        current_period_end=subscription.current_period_end,
        search_quota=quota.search_limit(subscription.plan),
        # Only a real provider subscription can be managed in a billing portal.
        can_manage=provider in ("stripe", "paypal"),
    )


@router.post("/checkout")
async def create_checkout(
    plan: str = Query(...),
    provider: str = Query("stripe", pattern="^(stripe|paypal)$"),
    user: CurrentUser = Depends(current_user),
) -> dict[str, str]:
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)


@router.post("/portal")
async def billing_portal(user: CurrentUser = Depends(current_user)) -> dict[str, str]:
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)


@router.post("/cancel")
async def cancel_subscription(user: CurrentUser = Depends(current_user)) -> dict[str, str]:
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)
