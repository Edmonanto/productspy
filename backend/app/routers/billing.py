"""/billing — checkout, portal, cancel, and provider webhooks.

Subscription state is written **only** from a verified webhook. The browser's
return from a checkout URL is never treated as proof of payment — anyone can
navigate to the success URL.
"""
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from .. import config, quota, repository
from ..auth import CurrentUser, current_user
from ..billing import paypal_provider, stripe_provider
from ..schemas import BillingStatus

log = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/status", response_model=BillingStatus)
async def get_status(user: CurrentUser = Depends(current_user)) -> BillingStatus:
    subscription, provider = await repository.subscription(user.id)
    return BillingStatus(
        plan=subscription.plan,
        status=subscription.status,
        provider=provider,
        current_period_end=subscription.current_period_end,
        search_quota=quota.search_limit(subscription.plan),
        can_manage=provider in ("stripe", "paypal"),
    )


@router.post("/checkout")
async def create_checkout(
    plan: str = Query(...),
    provider: str = Query("stripe", pattern="^(stripe|paypal)$"),
    user: CurrentUser = Depends(current_user),
) -> dict[str, str]:
    if plan not in config.PAID_PLANS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"'{plan}' is not a paid plan. Choose one of: "
            + ", ".join(config.PAID_PLANS),
        )

    row = await repository.subscription_row(user.id)
    if row and row["plan"] == plan and row["status"] == "active":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"You are already on the {plan} plan.",
        )

    if provider == "stripe":
        url = await stripe_provider.create_checkout(
            user.id, user.email, plan,
            customer_id=row["provider_customer_id"] if row else None,
        )
    else:
        url = await paypal_provider.create_checkout(user.id, user.email, plan)

    return {"checkout_url": url, "provider": provider}


@router.post("/portal")
async def billing_portal(user: CurrentUser = Depends(current_user)) -> dict[str, str]:
    row = await repository.subscription_row(user.id)
    if not row or row["provider"] not in ("stripe", "paypal"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="You don't have a paid subscription to manage.",
        )

    if row["provider"] == "paypal":
        # PayPal has no hosted portal we can create a session for.
        return {"portal_url": paypal_provider.portal_url()}

    if not row["provider_customer_id"]:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="No Stripe customer on file."
        )
    return {"portal_url": await stripe_provider.create_portal(row["provider_customer_id"])}


@router.post("/cancel")
async def cancel_subscription(
    user: CurrentUser = Depends(current_user),
) -> dict[str, str]:
    row = await repository.subscription_row(user.id)
    if not row or not row["provider_subscription_id"]:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="You don't have an active subscription."
        )

    if row["provider"] == "stripe":
        await stripe_provider.cancel(row["provider_subscription_id"])
    elif row["provider"] == "paypal":
        await paypal_provider.cancel(row["provider_subscription_id"])
    else:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="Unknown billing provider."
        )

    # The provider's webhook is the source of truth for the final state; this
    # just reflects the request immediately in the UI.
    await repository.upsert_subscription(
        user_id=user.id,
        plan=row["plan"],
        status=row["status"],
        provider=row["provider"],
        cancel_at_period_end=True,
    )
    return {"message": "Subscription will end at the close of the current period."}


# ── Webhooks (unauthenticated — the signature is the authentication) ────────
def _period_end(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):  # Stripe sends unix seconds
        return datetime.fromtimestamp(value, tz=timezone.utc)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


async def _apply(provider: str, parsed: dict[str, Any]) -> None:
    """Resolve the user and write the new subscription state."""
    user_id = parsed.get("user_id")
    if not user_id:
        # Events triggered from the provider's own dashboard carry no
        # metadata, so fall back to the ids we stored at checkout.
        user_id = await repository.find_user_by_provider_id(
            parsed.get("customer_id"), parsed.get("subscription_id")
        )
    if not user_id:
        log.warning("%s event could not be matched to a user: %s", provider, parsed)
        return

    await repository.upsert_subscription(
        user_id=user_id,
        plan=parsed.get("plan") or config.DEFAULT_PLAN,
        status=parsed["status"],
        provider=provider,
        customer_id=parsed.get("customer_id"),
        subscription_id=parsed.get("subscription_id"),
        current_period_end=_period_end(parsed.get("current_period_end")),
        cancel_at_period_end=parsed.get("cancel_at_period_end", False),
    )


@router.post("/webhook/stripe", include_in_schema=False)
async def stripe_webhook(request: Request) -> dict[str, str]:
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    event = stripe_provider.verify_webhook(payload, signature)

    event_id, event_type = event.get("id", ""), event.get("type", "")
    if not await repository.claim_billing_event("stripe", event_id, event_type):
        return {"status": "duplicate"}  # already applied

    try:
        parsed = stripe_provider.parse_event(event)
        if parsed:
            await _apply("stripe", parsed)
    except Exception as exc:
        # Record the failure, then 500 so Stripe retries.
        await repository.complete_billing_event("stripe", event_id, str(exc))
        log.exception("stripe webhook %s failed", event_id)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Webhook processing failed"
        )

    await repository.complete_billing_event("stripe", event_id)
    return {"status": "ok"}


@router.post("/webhook/paypal", include_in_schema=False)
async def paypal_webhook(request: Request) -> dict[str, str]:
    body = await request.json()
    if not await paypal_provider.verify_webhook(dict(request.headers), body):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid signature")

    event_id, event_type = body.get("id", ""), body.get("event_type", "")
    if not await repository.claim_billing_event("paypal", event_id, event_type):
        return {"status": "duplicate"}

    try:
        parsed = paypal_provider.parse_event(body)
        if parsed:
            await _apply("paypal", parsed)
    except Exception as exc:
        await repository.complete_billing_event("paypal", event_id, str(exc))
        log.exception("paypal webhook %s failed", event_id)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Webhook processing failed"
        )

    await repository.complete_billing_event("paypal", event_id)
    return {"status": "ok"}
