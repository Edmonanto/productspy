"""7-day free trial: access rules, /users/me, /billing/trial, Stripe trial_end."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import config, db, repository, trial
from app.auth import CurrentUser, current_user
from app.billing import stripe_provider
from app.main import app
from app.schemas import Subscription

NOW = datetime(2026, 10, 25, tzinfo=timezone.utc)
USER = CurrentUser(id="11111111-1111-1111-1111-111111111111", email="e@x.com",
                   name="Edmond", avatar_url=None)


def row(**kw) -> dict:
    base = {"plan": "pro", "status": "trialing", "provider": "none",
            "trial_ends_at": NOW + timedelta(days=3), "trial_used": True,
            "provider_customer_id": None, "provider_subscription_id": None}
    base.update(kw)
    return base


# ── pure rules ──────────────────────────────────────────────────────────────
def test_active_trial_is_pro():
    assert trial.effective_plan("pro", "trialing", "none", NOW + timedelta(hours=1), NOW) == "pro"
    info = trial.trial_info(row(), NOW)
    assert info["active"] and info["days_left"] == 3 and not info["eligible"] and not info["expired"]


def test_expired_trial_is_free_before_the_job_runs():
    assert trial.effective_plan("pro", "trialing", "none", NOW - timedelta(seconds=1), NOW) == "free"
    info = trial.trial_info(row(trial_ends_at=NOW - timedelta(days=1)), NOW)
    assert info["expired"] and not info["active"] and not info["eligible"]


def test_paid_subscriptions_are_not_trials():
    # Stripe maps its own 'trialing' to 'active', and writes its provider.
    assert trial.effective_plan("pro", "active", "stripe", NOW - timedelta(days=30), NOW) == "pro"
    assert trial.effective_plan("pro", "canceled", "stripe", None, NOW) == "free"


def test_legacy_free_account_is_eligible():
    info = trial.trial_info(row(plan="free", status="active", trial_used=False, trial_ends_at=None), NOW)
    assert info["eligible"] and not info["active"]


def test_no_row_means_free_and_eligible():
    info = trial.trial_info(None, NOW)
    assert info["eligible"] and info["length_days"] == config.TRIAL_DAYS


def test_reminder_copy_switches_to_today():
    assert "tomorrow" in trial.ending_email(40)[0]
    assert "today" in trial.ending_email(10)[0]


# ── routes ──────────────────────────────────────────────────────────────────
async def _noop(*_a, **_k):
    return None


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(db, "connect", _noop)
    monkeypatch.setattr(db, "disconnect", _noop)
    app.dependency_overrides[current_user] = lambda: USER
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_me_starts_trial_for_new_account(client, monkeypatch):
    calls = []
    current = row(trial_ends_at=datetime.now(timezone.utc) + timedelta(days=7))

    async def ensure(uid, email):
        calls.append((uid, email))

    async def sub(_uid):
        return Subscription(plan="pro", status="trialing", current_period_end=None), "none"

    async def sub_row(_uid):
        return current

    monkeypatch.setattr(repository, "ensure_subscription", ensure)
    monkeypatch.setattr(repository, "subscription", sub)
    monkeypatch.setattr(repository, "subscription_row", sub_row)

    body = client.get("/api/v1/users/me").json()
    assert calls == [(USER.id, USER.email)]
    assert body["trial"]["active"] and body["trial"]["days_left"] == 7
    assert body["subscription"]["plan"] == "pro"


def test_start_trial_once(client, monkeypatch):
    state = {"used": False}

    async def start(_uid, _email):
        if state["used"]:
            return False
        state["used"] = True
        return True

    async def sub_row(_uid):
        return row(trial_ends_at=datetime.now(timezone.utc) + timedelta(days=7))

    monkeypatch.setattr(repository, "ensure_subscription", _noop)
    monkeypatch.setattr(repository, "start_trial", start)
    monkeypatch.setattr(repository, "subscription_row", sub_row)

    first = client.post("/api/v1/billing/trial")
    assert first.status_code == 200 and first.json()["trial"]["active"]
    assert client.post("/api/v1/billing/trial").status_code == 400


def test_checkout_during_trial_defers_first_charge(client, monkeypatch):
    seen = {}
    ends = datetime.now(timezone.utc) + timedelta(days=5)

    async def sub_row(_uid):
        return row(trial_ends_at=ends)

    async def checkout(uid, email, plan, customer_id, trial_ends_at=None):
        seen["trial_ends_at"] = trial_ends_at
        return "https://checkout.stripe.test/s"

    monkeypatch.setattr(repository, "subscription_row", sub_row)
    monkeypatch.setattr(stripe_provider, "create_checkout", checkout)

    r = client.post("/api/v1/billing/checkout?plan=pro&provider=stripe")
    assert r.status_code == 200
    assert seen["trial_ends_at"] == ends


def test_checkout_after_trial_charges_now(client, monkeypatch):
    seen = {}

    async def sub_row(_uid):
        return row(plan="free", status="active", trial_ends_at=datetime.now(timezone.utc) - timedelta(days=2))

    async def checkout(uid, email, plan, customer_id, trial_ends_at=None):
        seen["trial_ends_at"] = trial_ends_at
        return "https://checkout.stripe.test/s"

    monkeypatch.setattr(repository, "subscription_row", sub_row)
    monkeypatch.setattr(stripe_provider, "create_checkout", checkout)

    assert client.post("/api/v1/billing/checkout?plan=pro&provider=stripe").status_code == 200
    assert seen["trial_ends_at"] is None


def test_stripe_trial_end_only_when_far_enough(monkeypatch):
    """Stripe rejects trial_end < 48h out, so closer than that we charge now."""
    created = {}

    class FakeSession:
        @staticmethod
        def create(**params):
            created.update(params)
            return type("S", (), {"url": "https://checkout"})()

    fake = type("stripe", (), {"checkout": type("c", (), {"Session": FakeSession})})
    monkeypatch.setattr(stripe_provider, "_client", lambda: fake)
    monkeypatch.setitem(config.STRIPE_PRICE_IDS, "pro", "price_pro")

    import asyncio
    soon = datetime.now(timezone.utc) + timedelta(hours=30)
    later = datetime.now(timezone.utc) + timedelta(days=4)
    asyncio.run(stripe_provider.create_checkout(USER.id, USER.email, "pro", None, trial_ends_at=soon))
    assert "trial_end" not in created["subscription_data"]
    asyncio.run(stripe_provider.create_checkout(USER.id, USER.email, "pro", None, trial_ends_at=later))
    assert created["subscription_data"]["trial_end"] == int(later.timestamp())
