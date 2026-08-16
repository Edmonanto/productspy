"""PayPal subscriptions via the REST API.

There is no current official Python SDK, so this talks to the v1 REST endpoints
directly. Webhook signatures are verified by calling PayPal's own
verify-webhook-signature endpoint — the payload alone is never trusted.
"""
import logging
from typing import Any

import httpx
from fastapi import HTTPException, status

from .. import config

log = logging.getLogger(__name__)


def configured() -> bool:
    return bool(config.PAYPAL_CLIENT_ID and config.PAYPAL_CLIENT_SECRET)


def _require_configured() -> None:
    if not configured():
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED, detail="PayPal is not configured."
        )


async def _token() -> str:
    _require_configured()
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{config.PAYPAL_API_BASE}/v1/oauth2/token",
            data={"grant_type": "client_credentials"},
            auth=(config.PAYPAL_CLIENT_ID, config.PAYPAL_CLIENT_SECRET),
            headers={"Accept": "application/json"},
        )
    if response.status_code != 200:
        log.error("paypal auth failed: %s", response.text)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail="PayPal auth failed")
    return response.json()["access_token"]


async def _request(method: str, path: str, **kwargs) -> dict[str, Any]:
    token = await _token()
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.request(
            method,
            f"{config.PAYPAL_API_BASE}{path}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            **kwargs,
        )
    if response.status_code >= 400:
        log.error("paypal %s %s -> %s %s", method, path, response.status_code, response.text)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail="PayPal request failed")
    return response.json() if response.content else {}


async def create_checkout(user_id: str, email: str, plan: str) -> str:
    plan_id = config.PAYPAL_PLAN_IDS.get(plan)
    if not plan_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"No PayPal plan configured for the {plan} plan.",
        )

    body: dict[str, Any] = {
        "plan_id": plan_id,
        # custom_id is what the webhook uses to find our user.
        "custom_id": user_id,
        "application_context": {
            "brand_name": "ProductSpy Pro",
            "user_action": "SUBSCRIBE_NOW",
            "return_url": f"{config.APP_URL}/dashboard/billing?checkout=success",
            "cancel_url": f"{config.APP_URL}/dashboard/billing?checkout=cancelled",
        },
    }
    if email:
        body["subscriber"] = {"email_address": email}

    data = await _request("POST", "/v1/billing/subscriptions", json=body)

    for link in data.get("links", []):
        if link.get("rel") == "approve":
            return link["href"]

    raise HTTPException(
        status.HTTP_502_BAD_GATEWAY, detail="PayPal did not return an approval link"
    )


async def cancel(subscription_id: str) -> None:
    await _request(
        "POST",
        f"/v1/billing/subscriptions/{subscription_id}/cancel",
        json={"reason": "Cancelled by user from ProductSpy Pro"},
    )


def portal_url() -> str:
    """PayPal has no equivalent of Stripe's billing portal.

    Send the user to their own PayPal automatic-payments page rather than
    pretending we can host one.
    """
    return "https://www.paypal.com/myaccount/autopay/"


async def verify_webhook(headers: dict[str, str], body: dict[str, Any]) -> bool:
    """Ask PayPal whether this delivery is genuine."""
    if not config.PAYPAL_WEBHOOK_ID:
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED,
            detail="PAYPAL_WEBHOOK_ID is not configured.",
        )

    lowered = {k.lower(): v for k, v in headers.items()}
    required = (
        "paypal-auth-algo", "paypal-cert-url", "paypal-transmission-id",
        "paypal-transmission-sig", "paypal-transmission-time",
    )
    if any(key not in lowered for key in required):
        return False

    result = await _request(
        "POST",
        "/v1/notifications/verify-webhook-signature",
        json={
            "auth_algo": lowered["paypal-auth-algo"],
            "cert_url": lowered["paypal-cert-url"],
            "transmission_id": lowered["paypal-transmission-id"],
            "transmission_sig": lowered["paypal-transmission-sig"],
            "transmission_time": lowered["paypal-transmission-time"],
            "webhook_id": config.PAYPAL_WEBHOOK_ID,
            "webhook_event": body,
        },
    )
    return result.get("verification_status") == "SUCCESS"


# PayPal subscription state -> ours. Anything not listed here is ignored.
_STATUS = {
    "BILLING.SUBSCRIPTION.ACTIVATED": "active",
    "BILLING.SUBSCRIPTION.RE-ACTIVATED": "active",
    "BILLING.SUBSCRIPTION.UPDATED": "active",
    "BILLING.SUBSCRIPTION.CANCELLED": "canceled",
    "BILLING.SUBSCRIPTION.EXPIRED": "canceled",
    "BILLING.SUBSCRIPTION.SUSPENDED": "past_due",
    "BILLING.SUBSCRIPTION.PAYMENT.FAILED": "past_due",
}


def parse_event(event: dict[str, Any]) -> dict[str, Any] | None:
    event_type = event.get("event_type", "")
    mapped = _STATUS.get(event_type)
    if mapped is None:
        return None

    resource = event.get("resource", {})
    plan_id = resource.get("plan_id", "")
    plan = next(
        (name for name, pid in config.PAYPAL_PLAN_IDS.items() if pid and pid == plan_id),
        None,
    )

    return {
        "user_id": resource.get("custom_id"),
        "plan": "free" if mapped == "canceled" else plan,
        "status": mapped,
        "customer_id": (resource.get("subscriber") or {}).get("payer_id"),
        "subscription_id": resource.get("id"),
        "current_period_end": (resource.get("billing_info") or {}).get(
            "next_billing_time"
        ),
        "cancel_at_period_end": False,
    }
