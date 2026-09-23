"""Phase 3: checkout guards, webhook verification, idempotency, event mapping."""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app import config, db, repository
from app.auth import CurrentUser, current_user
from app.billing import paypal_provider, stripe_provider
from app.main import app
from app.routers import billing as billing_router
from app.schemas import Subscription

USER = CurrentUser(id="11111111-1111-1111-1111-111111111111",
                   email="e@x.com", name="Edmond", avatar_url=None)


async def _noop():
    return None


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(db, "connect", lambda: _noop())
    monkeypatch.setattr(db, "disconnect", lambda: _noop())
    app.dependency_overrides[current_user] = lambda: USER
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def stub_row(monkeypatch, row):
    async def subscription_row(_uid):
        return row
    monkeypatch.setattr(repository, "subscription_row", subscription_row)


# ── checkout guards ─────────────────────────────────────────────────────────
def test_cannot_checkout_the_free_plan(client, monkeypatch):
    stub_row(monkeypatch, None)
    res = client.post("/api/v1/billing/checkout?plan=free&provider=stripe")
    assert res.status_code == 400
    assert "not a paid plan" in res.json()["detail"]


def test_cannot_checkout_unknown_plan(client, monkeypatch):
    stub_row(monkeypatch, None)
    assert client.post(
        "/api/v1/billing/checkout?plan=enterprise&provider=stripe"
    ).status_code == 400


def test_rejects_unknown_provider(client, monkeypatch):
    stub_row(monkeypatch, None)
    # pattern on the query param — never reaches a provider call
    assert client.post(
        "/api/v1/billing/checkout?plan=pro&provider=bitcoin"
    ).status_code == 422


def test_blocks_double_subscribing_to_current_plan(client, monkeypatch):
    stub_row(monkeypatch, {"plan": "pro", "status": "active",
                           "provider": "stripe", "provider_customer_id": "cus_1"})
    res = client.post("/api/v1/billing/checkout?plan=pro&provider=stripe")
    assert res.status_code == 400
    assert "already on the pro plan" in res.json()["detail"]


def test_checkout_returns_provider_url(client, monkeypatch):
    stub_row(monkeypatch, None)

    async def create_checkout(user_id, email, plan, customer_id):
        assert (user_id, plan) == (USER.id, "pro")
        return "https://checkout.stripe.com/c/session_123"

    monkeypatch.setattr(stripe_provider, "create_checkout", create_checkout)
    body = client.post("/api/v1/billing/checkout?plan=pro&provider=stripe").json()
    assert body == {
        "checkout_url": "https://checkout.stripe.com/c/session_123",
        "provider": "stripe",
    }


# ── portal / cancel ─────────────────────────────────────────────────────────
def test_portal_rejected_without_subscription(client, monkeypatch):
    stub_row(monkeypatch, None)
    assert client.post("/api/v1/billing/portal").status_code == 400


def test_paypal_portal_points_at_paypal(client, monkeypatch):
    stub_row(monkeypatch, {"plan": "pro", "status": "active", "provider": "paypal",
                           "provider_customer_id": None,
                           "provider_subscription_id": "I-1"})
    body = client.post("/api/v1/billing/portal").json()
    assert "paypal.com" in body["portal_url"]


def test_cancel_rejected_without_subscription(client, monkeypatch):
    stub_row(monkeypatch, None)
    assert client.post("/api/v1/billing/cancel").status_code == 400


def test_cancel_marks_period_end(client, monkeypatch):
    stub_row(monkeypatch, {"plan": "pro", "status": "active", "provider": "stripe",
                           "provider_customer_id": "cus_1",
                           "provider_subscription_id": "sub_1"})
    cancelled, saved = {}, {}

    async def cancel(sub_id):
        cancelled["id"] = sub_id

    async def upsert(**kwargs):
        saved.update(kwargs)

    monkeypatch.setattr(stripe_provider, "cancel", cancel)
    monkeypatch.setattr(repository, "upsert_subscription", upsert)

    assert client.post("/api/v1/billing/cancel").status_code == 200
    assert cancelled["id"] == "sub_1"
    # Access is kept until the period ends, not revoked immediately.
    assert saved["cancel_at_period_end"] is True
    assert saved["plan"] == "pro"


# ── webhook security ────────────────────────────────────────────────────────
def test_stripe_webhook_rejects_bad_signature(client, monkeypatch):
    def verify(payload, signature):
        from fastapi import HTTPException
        raise HTTPException(400, detail="Invalid signature")

    monkeypatch.setattr(stripe_provider, "verify_webhook", verify)
    res = client.post("/api/v1/billing/webhook/stripe",
                      json={"id": "evt_1", "type": "checkout.session.completed"})
    assert res.status_code == 400


def test_paypal_webhook_rejects_unverified(client, monkeypatch):
    async def verify(headers, body):
        return False

    monkeypatch.setattr(paypal_provider, "verify_webhook", verify)
    res = client.post("/api/v1/billing/webhook/paypal",
                      json={"id": "WH-1", "event_type": "BILLING.SUBSCRIPTION.ACTIVATED"})
    assert res.status_code == 400


def test_duplicate_event_is_not_applied_twice(client, monkeypatch):
    event = {"id": "evt_dup", "type": "checkout.session.completed",
             "data": {"object": {"client_reference_id": USER.id,
                                 "metadata": {"user_id": USER.id, "plan": "pro"},
                                 "customer": "cus_1", "subscription": "sub_1"}}}
    monkeypatch.setattr(stripe_provider, "verify_webhook", lambda p, s: event)
    applied = []

    async def claim(provider, event_id, event_type):
        return False  # already seen

    async def upsert(**kwargs):
        applied.append(kwargs)

    monkeypatch.setattr(repository, "claim_billing_event", claim)
    monkeypatch.setattr(repository, "upsert_subscription", upsert)

    res = client.post("/api/v1/billing/webhook/stripe", json={})
    assert res.json() == {"status": "duplicate"}
    assert applied == []  # the replay changed nothing


def test_verified_event_upgrades_the_user(client, monkeypatch):
    event = {"id": "evt_ok", "type": "checkout.session.completed",
             "data": {"object": {"client_reference_id": USER.id,
                                 "metadata": {"user_id": USER.id, "plan": "pro"},
                                 "customer": "cus_1", "subscription": "sub_1"}}}
    monkeypatch.setattr(stripe_provider, "verify_webhook", lambda p, s: event)
    saved = {}

    async def claim(provider, event_id, event_type):
        return True

    async def complete(provider, event_id, error=None):
        saved["error"] = error

    async def upsert(**kwargs):
        saved.update(kwargs)

    monkeypatch.setattr(repository, "claim_billing_event", claim)
    monkeypatch.setattr(repository, "complete_billing_event", complete)
    monkeypatch.setattr(repository, "upsert_subscription", upsert)

    assert client.post("/api/v1/billing/webhook/stripe", json={}).json() == {"status": "ok"}
    assert saved["user_id"] == USER.id
    assert saved["plan"] == "pro"
    assert saved["status"] == "active"
    assert saved["error"] is None


def test_unmatched_event_does_not_write(client, monkeypatch):
    """An event with no metadata and no stored ids must not guess a user."""
    event = {"id": "evt_orphan", "type": "customer.subscription.deleted",
             "data": {"object": {"id": "sub_x", "customer": "cus_x", "metadata": {}}}}
    monkeypatch.setattr(stripe_provider, "verify_webhook", lambda p, s: event)
    applied = []

    async def claim(*a):
        return True

    async def complete(*a, **k):
        return None

    async def find(customer_id, subscription_id):
        return None

    async def upsert(**kwargs):
        applied.append(kwargs)

    monkeypatch.setattr(repository, "claim_billing_event", claim)
    monkeypatch.setattr(repository, "complete_billing_event", complete)
    monkeypatch.setattr(repository, "find_user_by_provider_id", find)
    monkeypatch.setattr(repository, "upsert_subscription", upsert)

    assert client.post("/api/v1/billing/webhook/stripe", json={}).json() == {"status": "ok"}
    assert applied == []


# ── event mapping (pure) ────────────────────────────────────────────────────
def test_stripe_past_due_keeps_its_own_status():
    parsed = stripe_provider.parse_event({
        "type": "customer.subscription.updated",
        "data": {"object": {"id": "sub_1", "customer": "cus_1", "status": "past_due",
                            "metadata": {"user_id": "u", "plan": "pro"}}},
    })
    assert parsed["status"] == "past_due"


def test_stripe_trialing_counts_as_active():
    parsed = stripe_provider.parse_event({
        "type": "customer.subscription.updated",
        "data": {"object": {"id": "s", "customer": "c", "status": "trialing",
                            "metadata": {"user_id": "u", "plan": "pro"}}},
    })
    assert parsed["status"] == "active"


def test_stripe_deletion_drops_to_free():
    parsed = stripe_provider.parse_event({
        "type": "customer.subscription.deleted",
        "data": {"object": {"id": "s", "customer": "c", "metadata": {"user_id": "u"}}},
    })
    assert (parsed["plan"], parsed["status"]) == ("free", "canceled")


def test_stripe_ignores_irrelevant_events():
    assert stripe_provider.parse_event({"type": "invoice.created", "data": {"object": {}}}) is None


def test_paypal_cancellation_drops_to_free():
    parsed = paypal_provider.parse_event({
        "event_type": "BILLING.SUBSCRIPTION.CANCELLED",
        "resource": {"id": "I-1", "custom_id": "u1", "plan_id": "P-x"},
    })
    assert (parsed["plan"], parsed["status"]) == ("free", "canceled")
    assert parsed["user_id"] == "u1"


def test_paypal_suspension_is_past_due():
    parsed = paypal_provider.parse_event({
        "event_type": "BILLING.SUBSCRIPTION.SUSPENDED",
        "resource": {"id": "I-1", "custom_id": "u1"},
    })
    assert parsed["status"] == "past_due"


def test_paypal_ignores_irrelevant_events():
    assert paypal_provider.parse_event({"event_type": "CHECKOUT.ORDER.APPROVED"}) is None


# ── period-end coercion ─────────────────────────────────────────────────────
def test_period_end_accepts_unix_and_iso():
    unix = billing_router._period_end(1893456000)
    iso = billing_router._period_end("2030-01-01T00:00:00Z")
    assert unix.tzinfo is not None and iso.tzinfo is not None
    assert billing_router._period_end(None) is None
    assert billing_router._period_end("not-a-date") is None
