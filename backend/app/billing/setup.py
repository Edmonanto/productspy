"""One-time payment setup — creates everything ProductSpy needs in YOUR Stripe
and PayPal accounts, and writes the resulting ids into backend/.env.

    python -m app.billing.setup stripe     # products + monthly prices, webhook, customer portal
    python -m app.billing.setup paypal     # product, monthly plans (+ partner-discount plans), webhook
    python -m app.billing.setup render     # print the lines to paste into Render (from .env)

Safe to run again: existing prices/plans/webhooks are found and reused.
Keys are read from backend/.env (STRIPE_SECRET_KEY, PAYPAL_CLIENT_ID,
PAYPAL_CLIENT_SECRET, PAYPAL_API_BASE) and never printed in full.
Test keys (sk_test_, sandbox PayPal) create test objects; live keys create live ones.
"""
from __future__ import annotations

import asyncio
import pathlib
import sys
from decimal import Decimal

import httpx

from .. import config

ENV = pathlib.Path(__file__).resolve().parents[2] / ".env"
PLAN_NAMES = {"starter": "Starter", "pro": "Pro", "agency": "Agency"}
PARTNER_DISCOUNT_PCT = 25          # PayPal can't take coupons: partner plans bill month 1 at -25%

STRIPE_EVENTS = [
    "checkout.session.completed", "customer.subscription.created", "customer.subscription.updated",
    "customer.subscription.deleted", "invoice.paid", "charge.refunded",
]
PAYPAL_EVENTS = [
    "BILLING.SUBSCRIPTION.ACTIVATED", "BILLING.SUBSCRIPTION.RE-ACTIVATED", "BILLING.SUBSCRIPTION.UPDATED",
    "BILLING.SUBSCRIPTION.CANCELLED", "BILLING.SUBSCRIPTION.EXPIRED", "BILLING.SUBSCRIPTION.SUSPENDED",
    "BILLING.SUBSCRIPTION.PAYMENT.FAILED", "PAYMENT.SALE.COMPLETED", "PAYMENT.SALE.REFUNDED",
    "PAYMENT.SALE.REVERSED",
]


# ── .env helpers ─────────────────────────────────────────────────────────────
def write_env(values: dict[str, str]) -> None:
    lines = ENV.read_text().splitlines() if ENV.exists() else []
    seen = set()
    for i, line in enumerate(lines):
        key = line.split("=", 1)[0].strip()
        if key in values:
            lines[i] = f"{key}={values[key]}"
            seen.add(key)
    lines += [f"{k}={v}" for k, v in values.items() if k not in seen]
    ENV.write_text("\n".join(lines) + "\n")


def read_env() -> dict[str, str]:
    out = {}
    if ENV.exists():
        for line in ENV.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    return out


def mask(v: str) -> str:
    return v if len(v) < 12 else f"{v[:8]}…{v[-4:]}"


def webhook_url(provider: str) -> str:
    return f"{config.API_PUBLIC_URL}/billing/webhook/{provider}"


# ── Stripe ───────────────────────────────────────────────────────────────────
def setup_stripe() -> dict[str, str]:
    import stripe

    key = config.STRIPE_SECRET_KEY
    if not key:
        sys.exit("STRIPE_SECRET_KEY is missing from backend/.env")
    stripe.api_key = key
    live = key.startswith(("sk_live", "rk_live"))
    print(f"Stripe {'LIVE' if live else 'TEST'} mode")
    out: dict[str, str] = {}

    for plan, name in PLAN_NAMES.items():
        cents = int(Decimal(str(config.PLAN_PRICES_USD[plan])) * 100)
        lookup = f"productspy_{plan}_monthly_{cents}"
        found = stripe.Price.list(lookup_keys=[lookup], active=True, limit=1).data
        if found:
            price = found[0]
            print(f"  {name}: reusing price {price.id} (${cents / 100:.2f}/month)")
        else:
            product = stripe.Product.create(name=f"ProductSpy Pro — {name}",
                                            metadata={"productspy_plan": plan})
            price = stripe.Price.create(product=product.id, currency="usd", unit_amount=cents,
                                        recurring={"interval": "month"}, lookup_key=lookup,
                                        transfer_lookup_key=True, metadata={"productspy_plan": plan})
            print(f"  {name}: created price {price.id} (${cents / 100:.2f}/month)")
        out[f"STRIPE_PRICE_{plan.upper()}"] = price.id

    url = webhook_url("stripe")
    existing = [w for w in stripe.WebhookEndpoint.list(limit=100).data if w.url == url]
    have_secret = bool(config.STRIPE_WEBHOOK_SECRET) and existing
    if existing and have_secret:
        stripe.WebhookEndpoint.modify(existing[0].id, enabled_events=STRIPE_EVENTS)
        print(f"  Webhook: updated events on {existing[0].id} (secret unchanged)")
    else:
        for w in existing:   # Stripe only reveals a secret at creation: replace it
            stripe.WebhookEndpoint.delete(w.id)
        wh = stripe.WebhookEndpoint.create(url=url, enabled_events=STRIPE_EVENTS,
                                           description="ProductSpy Pro subscriptions + partner commissions")
        out["STRIPE_WEBHOOK_SECRET"] = wh.secret
        print(f"  Webhook: created {wh.id} -> {url}")

    if not [c for c in stripe.billing_portal.Configuration.list(limit=10).data if c.active]:
        stripe.billing_portal.Configuration.create(
            business_profile={"headline": "Manage your ProductSpy Pro subscription"},
            features={"customer_update": {"enabled": True, "allowed_updates": ["email", "address"]},
                      "invoice_history": {"enabled": True},
                      "payment_method_update": {"enabled": True},
                      "subscription_cancel": {"enabled": True, "mode": "at_period_end"}})
        print("  Customer portal: configured (invoices, card update, cancel)")
    else:
        print("  Customer portal: already configured")
    return out


# ── PayPal ───────────────────────────────────────────────────────────────────
async def _paypal(client: httpx.AsyncClient, method: str, path: str, **kw) -> dict:
    r = await client.request(method, f"{config.PAYPAL_API_BASE}{path}", **kw)
    if r.status_code >= 400:
        sys.exit(f"PayPal {method} {path} failed: {r.status_code} {r.text[:400]}")
    return r.json() if r.content else {}


def _plan_body(product_id: str, plan: str, partner: bool) -> dict:
    price = Decimal(str(config.PLAN_PRICES_USD[plan]))
    regular = {"frequency": {"interval_unit": "MONTH", "interval_count": 1}, "tenure_type": "REGULAR",
               "sequence": 2 if partner else 1, "total_cycles": 0,
               "pricing_scheme": {"fixed_price": {"value": f"{price:.2f}", "currency_code": "USD"}}}
    cycles = [regular]
    if partner:
        first = (price * (100 - PARTNER_DISCOUNT_PCT) / 100).quantize(Decimal("0.01"))
        cycles.insert(0, {"frequency": {"interval_unit": "MONTH", "interval_count": 1}, "tenure_type": "TRIAL",
                          "sequence": 1, "total_cycles": 1,
                          "pricing_scheme": {"fixed_price": {"value": f"{first:.2f}", "currency_code": "USD"}}})
    return {"product_id": product_id, "status": "ACTIVE",
            "name": f"ProductSpy {PLAN_NAMES[plan]} — ${price}/month" + (f" (partner: {PARTNER_DISCOUNT_PCT}% off month 1)" if partner else ""),
            "billing_cycles": cycles,
            "payment_preferences": {"auto_bill_outstanding": True, "payment_failure_threshold": 2,
                                    "setup_fee_failure_action": "CONTINUE"}}


async def setup_paypal() -> dict[str, str]:
    if not (config.PAYPAL_CLIENT_ID and config.PAYPAL_CLIENT_SECRET):
        sys.exit("PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET are missing from backend/.env")
    live = "sandbox" not in config.PAYPAL_API_BASE
    print(f"PayPal {'LIVE' if live else 'SANDBOX'} ({config.PAYPAL_API_BASE})")
    out: dict[str, str] = {}
    async with httpx.AsyncClient(timeout=40) as client:
        tok = await client.post(f"{config.PAYPAL_API_BASE}/v1/oauth2/token", data={"grant_type": "client_credentials"},
                                auth=(config.PAYPAL_CLIENT_ID, config.PAYPAL_CLIENT_SECRET))
        if tok.status_code != 200:
            sys.exit(f"PayPal login failed ({tok.status_code}) — check the client id/secret and PAYPAL_API_BASE "
                     "(live: https://api-m.paypal.com, sandbox: https://api-m.sandbox.paypal.com)")
        client.headers.update({"Authorization": f"Bearer {tok.json()['access_token']}",
                               "Content-Type": "application/json", "Prefer": "return=representation"})

        products = (await _paypal(client, "GET", "/v1/catalogs/products?page_size=20")).get("products", [])
        prod = next((p for p in products if p.get("name") == "ProductSpy Pro"), None)
        if not prod:
            prod = await _paypal(client, "POST", "/v1/catalogs/products", json={
                "name": "ProductSpy Pro", "description": "Daily winning products for dropshippers",
                "type": "SERVICE", "category": "SOFTWARE", "home_url": config.APP_URL})
            print(f"  Product: created {prod['id']}")
        else:
            print(f"  Product: reusing {prod['id']}")

        plans = (await _paypal(client, "GET", f"/v1/billing/plans?product_id={prod['id']}&page_size=20")).get("plans", [])
        for plan in PLAN_NAMES:
            for partner in (False, True):
                body = _plan_body(prod["id"], plan, partner)
                hit = next((p for p in plans if p.get("name") == body["name"] and p.get("status") == "ACTIVE"), None)
                if not hit:
                    hit = await _paypal(client, "POST", "/v1/billing/plans", json=body)
                    print(f"  Plan: created {hit['id']} — {body['name']}")
                else:
                    print(f"  Plan: reusing {hit['id']} — {body['name']}")
                out[f"PAYPAL_{'PARTNER_' if partner else ''}PLAN_{plan.upper()}"] = hit["id"]

        # Retire plans at old prices so nobody can subscribe to them any more
        # (existing subscribers on them keep their price).
        keep = {v for k, v in out.items() if "PLAN" in k}
        for p in plans:
            if p.get("status") == "ACTIVE" and p["id"] not in keep and str(p.get("name", "")).startswith("ProductSpy"):
                await _paypal(client, "POST", f"/v1/billing/plans/{p['id']}/deactivate")
                print(f"  Plan: deactivated old {p['id']} — {p.get('name')}")

        url = webhook_url("paypal")
        hooks = (await _paypal(client, "GET", "/v1/notifications/webhooks")).get("webhooks", [])
        hook = next((h for h in hooks if h.get("url") == url), None)
        types = [{"name": n} for n in PAYPAL_EVENTS]
        if hook:
            await _paypal(client, "PATCH", f"/v1/notifications/webhooks/{hook['id']}",
                          json=[{"op": "replace", "path": "/event_types", "value": types}])
            print(f"  Webhook: updated {hook['id']}")
        else:
            hook = await _paypal(client, "POST", "/v1/notifications/webhooks", json={"url": url, "event_types": types})
            print(f"  Webhook: created {hook['id']} -> {url}")
        out["PAYPAL_WEBHOOK_ID"] = hook["id"]
    return out


RENDER_KEYS = ["STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", "STRIPE_PRICE_STARTER", "STRIPE_PRICE_PRO",
               "STRIPE_PRICE_AGENCY", "PAYPAL_CLIENT_ID", "PAYPAL_CLIENT_SECRET", "PAYPAL_API_BASE",
               "PAYPAL_WEBHOOK_ID", "PAYPAL_PLAN_STARTER", "PAYPAL_PLAN_PRO", "PAYPAL_PLAN_AGENCY",
               "PAYPAL_PARTNER_PLAN_STARTER", "PAYPAL_PARTNER_PLAN_PRO", "PAYPAL_PARTNER_PLAN_AGENCY"]


def main() -> None:
    what = sys.argv[1] if len(sys.argv) > 1 else ""
    if what == "stripe":
        vals = setup_stripe()
    elif what == "paypal":
        vals = asyncio.run(setup_paypal())
    elif what == "render":
        env = read_env()
        print("# Paste these into Render → productspy-api → Environment (keep them private):")
        for k in RENDER_KEYS:
            if env.get(k):
                print(f"{k}={env[k]}")
        missing = [k for k in RENDER_KEYS if not env.get(k)]
        if missing:
            print("# not set yet:", ", ".join(missing))
        return
    else:
        sys.exit(__doc__)
    write_env(vals)
    print("\nSaved to backend/.env:")
    for k, v in vals.items():
        print(f"  {k}={mask(v)}")
    print("\nNext: python -m app.billing.setup render   (then paste into Render → productspy-api → Environment)")


if __name__ == "__main__":
    main()
