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


async def _send(method: str, path: str, **kwargs) -> httpx.Response:
    token = await _token()
    async with httpx.AsyncClient(timeout=30) as client:
        return await client.request(
            method,
            f"{config.PAYPAL_API_BASE}{path}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            **kwargs,
        )


async def _request(method: str, path: str, **kwargs) -> dict[str, Any]:
    response = await _send(method, path, **kwargs)
    if response.status_code >= 400:
        log.error("paypal %s %s -> %s %s", method, path, response.status_code, response.text)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail="PayPal request failed")
    return response.json() if response.content else {}


# Plan names as app/billing/setup.py creates them: "ProductSpy Pro — $69.99/month",
# partner plans add " (partner: 25% off month 1)".
_TIER_NAME = {"starter": "Starter", "pro": "Pro", "agency": "Agency"}
_replacement: dict[str, str] = {}   # inactive plan id -> active plan id found for it


async def _reactivate(plan_id: str) -> bool:
    """Switch our own configured plan back on (POST .../activate). The plan ids
    on Render are the ones setup.py created at the current prices, so ACTIVE is
    their intended state; PayPal answers 204 on success."""
    response = await _send("POST", f"/v1/billing/plans/{plan_id}/activate")
    if response.status_code >= 400:
        log.error("paypal activate %s -> %s %s", plan_id, response.status_code, response.text[:300])
        return False
    _replacement.pop(plan_id, None)
    return True


async def _active_plan_like(plan_id: str, plan: str, partner: bool) -> str | None:
    """The ACTIVE ProductSpy plan for this tier, when the configured one has been
    deactivated in PayPal (re-running setup, or by hand)."""
    if plan_id in _replacement:
        return _replacement[plan_id]
    product_id = (await _request("GET", f"/v1/billing/plans/{plan_id}")).get("product_id")
    if not product_id:
        return None
    listing = await _request("GET", f"/v1/billing/plans?product_id={product_id}&page_size=20")
    prefix = f"ProductSpy {_TIER_NAME[plan]} — "
    for p in listing.get("plans", []):
        name = str(p.get("name", ""))
        if p.get("status") == "ACTIVE" and name.startswith(prefix) and ("(partner" in name) == partner:
            _replacement[plan_id] = p["id"]
            return p["id"]
    return None


async def create_checkout(user_id: str, email: str, plan: str, partner_discount: bool = False) -> str:
    # Referred customers get the partner plan (first month at the partner discount).
    plan_id = (partner_discount and config.PAYPAL_PARTNER_PLAN_IDS.get(plan)) or config.PAYPAL_PLAN_IDS.get(plan)
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

    response = await _send("POST", "/v1/billing/subscriptions", json=body)
    if response.status_code == 422 and "PLAN_STATUS_INVALID" in response.text:
        partner = plan_id != config.PAYPAL_PLAN_IDS.get(plan)
        env = f"PAYPAL_{'PARTNER_' if partner else ''}PLAN_{plan.upper()}"
        active = await _active_plan_like(plan_id, plan, partner)
        log.error("paypal: %s=%s is not ACTIVE in PayPal; %s", env, plan_id,
                  f"using active plan {active} — set {env}={active} on Render" if active
                  else "no active ProductSpy plan found for this tier — run `python -m app.billing.setup paypal`")
        if not active and await _reactivate(plan_id):
            active = plan_id
            log.error("paypal: re-activated %s=%s in PayPal (it had been deactivated)", env, plan_id)
        if active:
            body["plan_id"] = active
            response = await _send("POST", "/v1/billing/subscriptions", json=body)
    if response.status_code >= 400:
        log.error("paypal POST /v1/billing/subscriptions -> %s %s", response.status_code, response.text)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail="PayPal checkout isn't available right now. Please pay by card, or try PayPal again later.",
        )
    data = response.json() if response.content else {}

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


async def tier_for_plan(plan_id: str) -> str | None:
    """Our tier for a PayPal plan id that isn't in the PAYPAL_*PLAN_* settings
    (e.g. the active plan checkout fell back to): read it from the plan's name."""
    if not plan_id:
        return None
    try:
        name = str((await _request("GET", f"/v1/billing/plans/{plan_id}")).get("name", ""))
    except HTTPException:
        return None
    for tier, label in _TIER_NAME.items():
        if name.startswith(f"ProductSpy {label} — "):
            return tier
    return None


def parse_event(event: dict[str, Any]) -> dict[str, Any] | None:
    event_type = event.get("event_type", "")
    mapped = _STATUS.get(event_type)
    if mapped is None:
        return None

    resource = event.get("resource", {})
    plan_id = resource.get("plan_id", "")
    # Partner-referred customers subscribe to the partner (first-month discount)
    # plan of the same tier: it must map to that tier, not fall through to free.
    plan = next(
        (name for ids in (config.PAYPAL_PLAN_IDS, config.PAYPAL_PARTNER_PLAN_IDS)
         for name, pid in ids.items() if pid and pid == plan_id),
        None,
    )
    if plan is None and mapped != "canceled":
        log.error("paypal %s for unknown plan_id %s — not in PAYPAL_PLAN_* or PAYPAL_PARTNER_PLAN_*",
                  event_type, plan_id)

    return {
        "plan_id": plan_id,
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
