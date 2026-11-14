"""Owner emails: signups, new subscribers, daily usage report."""
import pytest

from app import config, owner_notify, trial
from app.routers import billing


@pytest.fixture
def outbox(monkeypatch):
    sent = []

    async def fake_send(to, subject, html, reply_to=None):
        sent.append({"to": to, "subject": subject, "html": html, "reply_to": reply_to})
        return True

    monkeypatch.setattr(config, "RESEND_API_KEY", "k")
    monkeypatch.setattr(config, "NOTIFY_EMAILS", {"me@x.com"})
    monkeypatch.setattr(trial, "send_email", fake_send)
    return sent


def test_recipients_default(monkeypatch):
    monkeypatch.setattr(config, "NOTIFY_EMAILS", set())
    monkeypatch.setattr(config, "ADMIN_EMAILS", {"boss@x.com"})
    monkeypatch.setattr(config, "SUPPORT_EMAIL", "Help@x.com")
    assert owner_notify.recipients() == ["boss@x.com", "help@x.com"]


@pytest.mark.asyncio
async def test_signup_email(outbox):
    assert await owner_notify.notify_signup("new@shop.com", "Ana", "fr") == 1
    assert outbox[0]["subject"] == "New signup: new@shop.com"
    assert outbox[0]["reply_to"] == "new@shop.com" and "FR" in outbox[0]["html"]


class _Row(dict):
    pass


async def _apply_with(monkeypatch, before, parsed):
    async def row(_uid):
        return before

    async def upsert(**kw):
        return None

    async def rec(*a, **k):
        return None

    monkeypatch.setattr(billing.repository, "subscription_row", row)
    monkeypatch.setattr(billing.repository, "upsert_subscription", upsert)
    monkeypatch.setattr(billing.funnel, "record", rec)
    await billing._apply("stripe", parsed)


@pytest.mark.asyncio
async def test_new_subscriber_emails_once(outbox, monkeypatch):
    paid = {"user_id": "u1", "plan": "pro", "status": "active"}
    trialing = _Row(plan="pro", status="trialing", provider="none", email="a@b.com")
    await _apply_with(monkeypatch, trialing, paid)
    assert len(outbox) == 1 and "a@b.com → pro" in outbox[0]["subject"]

    # Renewal webhook: already paying on the same plan → no second email.
    active = _Row(plan="pro", status="active", provider="stripe", email="a@b.com")
    await _apply_with(monkeypatch, active, paid)
    assert len(outbox) == 1


def test_daily_report_email(monkeypatch):
    monkeypatch.setattr(config, "APIFY_MONTHLY_BUDGET_USD", 30.0)
    usage = {"days": [("2026-11-09", 0.9), ("2026-11-10", 1.25)], "cycle_usd": 25.0, "cycle_end": "2026-12-12"}
    subject, html = owner_notify.report_email(usage, ["x@y.com"], [], "2026-11-10")
    assert "Apify $0.90 yesterday" in subject and "$25.00/$30" in subject and "1 signup" in subject
    assert "83% of the monthly" in html and "x@y.com" in html
    subject, _ = owner_notify.report_email(None, [], [], "2026-11-10")
    assert "unavailable" in subject
