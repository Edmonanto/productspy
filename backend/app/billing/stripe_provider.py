"""Stripe checkout, portal, cancel, and webhook handling.

Subscription state is only ever written from a *verified* webhook, never from
the browser's redirect back to the success URL — a user can hit that URL
without paying, so trusting it would hand out free upgrades.
"""
import logging
from typing import Any

from fastapi import HTTPException, status

from .. import config

log = logging.getLogger(__name__)


def _client():
    try:
        import stripe
    except ImportError:
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED,
            detail="Stripe support is not installed on this server.",
        )
    if not config.STRIPE_SECRET_KEY:
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED,
            detail="Stripe is not configured.",
        )
    stripe.api_key = config.STRIPE_SECRET_KEY
    return stripe


def configured() -> bool:
    return bool(config.STRIPE_SECRET_KEY)


async def create_checkout(user_id: str, email: str, plan: str, customer_id: str | None) -> str:
    stripe = _client()
    price_id = config.STRIPE_PRICE_IDS.get(plan)
    if not price_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"No Stripe price configured for the {plan} plan.",
        )

    params: dict[str, Any] = {
        "mode": "subscription",
        "line_items": [{"price": price_id, "quantity": 1}],
        "success_url": f"{config.APP_URL}/dashboard/billing?checkout=success",
        "cancel_url": f"{config.APP_URL}/dashboard/billing?checkout=cancelled",
        # client_reference_id is how the webhook maps this back to our user.
        "client_reference_id": user_id,
        "metadata": {"user_id": user_id, "plan": plan},
        "subscription_data": {"metadata": {"user_id": user_id, "plan": plan}},
    }
    # Reuse the existing customer so a returning subscriber doesn't end up
    # with duplicate Stripe customers.
    if customer_id:
        params["customer"] = customer_id
    elif email:
        params["customer_email"] = email

    try:
        session = stripe.checkout.Session.create(**params)
    except Exception as exc:
        log.exception("stripe checkout failed for %s", user_id)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    return session.url


async def create_portal(customer_id: str) -> str:
    stripe = _client()
    try:
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=f"{config.APP_URL}/dashboard/billing",
        )
    except Exception as exc:
        log.exception("stripe portal failed for %s", customer_id)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return session.url


async def cancel(subscription_id: str) -> None:
    """Cancel at period end — the user keeps what they paid for."""
    stripe = _client()
    try:
        stripe.Subscription.modify(subscription_id, cancel_at_period_end=True)
    except Exception as exc:
        log.exception("stripe cancel failed for %s", subscription_id)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(exc))


def verify_webhook(payload: bytes, signature: str) -> dict[str, Any]:
    """Verify the Stripe signature and return the event.

    An unverified payload is an unauthenticated request to change someone's
    plan, so a failure here is a 400 and nothing is written.
    """
    stripe = _client()
    if not config.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED,
            detail="STRIPE_WEBHOOK_SECRET is not configured.",
        )
    try:
        return stripe.Webhook.construct_event(
            payload, signature, config.STRIPE_WEBHOOK_SECRET
        )
    except Exception as exc:
        log.warning("stripe webhook verification failed: %s", exc)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid signature")


def parse_event(event: dict[str, Any]) -> dict[str, Any] | None:
    """Map a Stripe event to the fields we store, or None to ignore it."""
    event_type = event.get("type", "")
    obj = event.get("data", {}).get("object", {})

    if event_type == "checkout.session.completed":
        return {
            "user_id": obj.get("client_reference_id")
            or (obj.get("metadata") or {}).get("user_id"),
            "plan": (obj.get("metadata") or {}).get("plan"),
            "status": "active",
            "customer_id": obj.get("customer"),
            "subscription_id": obj.get("subscription"),
            "current_period_end": None,
            "cancel_at_period_end": False,
        }

    if event_type in ("customer.subscription.updated", "customer.subscription.created"):
        return {
            "user_id": (obj.get("metadata") or {}).get("user_id"),
            "plan": (obj.get("metadata") or {}).get("plan"),
            # past_due keeps access while Stripe retries; unpaid/canceled don't.
            "status": _map_status(obj.get("status", "")),
            "customer_id": obj.get("customer"),
            "subscription_id": obj.get("id"),
            "current_period_end": obj.get("current_period_end"),
            "cancel_at_period_end": bool(obj.get("cancel_at_period_end")),
        }

    if event_type == "customer.subscription.deleted":
        return {
            "user_id": (obj.get("metadata") or {}).get("user_id"),
            "plan": "free",
            "status": "canceled",
            "customer_id": obj.get("customer"),
            "subscription_id": obj.get("id"),
            "current_period_end": obj.get("current_period_end"),
            "cancel_at_period_end": False,
        }

    return None


def _map_status(stripe_status: str) -> str:
    if stripe_status in ("active", "trialing"):
        return "active"
    if stripe_status == "past_due":
        return "past_due"
    return "canceled"
