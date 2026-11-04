"""PayPal checkout survives a deactivated plan id (PLAN_STATUS_INVALID)."""
import httpx
import pytest
from fastapi import HTTPException

from app import config
from app.billing import paypal_provider as pp


def _resp(code, json=None, text=None):
    return httpx.Response(code, json=json) if json is not None else httpx.Response(code, text=text or "")


@pytest.fixture(autouse=True)
def _plans(monkeypatch):
    monkeypatch.setitem(config.PAYPAL_PLAN_IDS, "pro", "P-OLD-PRO")
    monkeypatch.setitem(config.PAYPAL_PARTNER_PLAN_IDS, "pro", "P-OLD-PARTNER-PRO")
    pp._replacement.clear()


def _fake(monkeypatch, plans, accept):
    sent = []

    async def send(method, path, **kw):
        if method == "POST" and path == "/v1/billing/subscriptions":
            pid = kw["json"]["plan_id"]
            sent.append(pid)
            if pid in accept:
                return _resp(201, {"links": [{"rel": "approve", "href": f"https://paypal/approve/{pid}"}]})
            return _resp(422, text='{"name":"UNPROCESSABLE_ENTITY","details":[{"issue":"PLAN_STATUS_INVALID"}]}')
        if path.startswith("/v1/billing/plans/"):
            return _resp(200, {"id": path.rsplit("/", 1)[1], "product_id": "PROD-1"})
        if path.startswith("/v1/billing/plans?product_id=PROD-1"):
            return _resp(200, {"plans": plans})
        raise AssertionError(path)

    monkeypatch.setattr(pp, "_send", send)
    return sent


PLANS = [
    {"id": "P-OLD-PRO", "status": "INACTIVE", "name": "ProductSpy Pro — $69.99/month"},
    {"id": "P-NEW-PARTNER-PRO", "status": "ACTIVE", "name": "ProductSpy Pro — $69.99/month (partner: 25% off month 1)"},
    {"id": "P-NEW-STARTER", "status": "ACTIVE", "name": "ProductSpy Starter — $19.99/month"},
    {"id": "P-NEW-PRO", "status": "ACTIVE", "name": "ProductSpy Pro — $69.99/month"},
]


async def test_inactive_plan_falls_back_to_the_active_plan_of_that_tier(monkeypatch):
    sent = _fake(monkeypatch, PLANS, accept={"P-NEW-PRO", "P-NEW-PARTNER-PRO"})
    assert await pp.create_checkout("u1", "a@b.c", "pro") == "https://paypal/approve/P-NEW-PRO"
    assert sent == ["P-OLD-PRO", "P-NEW-PRO"]
    assert await pp.create_checkout("u1", "a@b.c", "pro", partner_discount=True) \
        == "https://paypal/approve/P-NEW-PARTNER-PRO"


async def test_no_active_plan_gives_a_clear_message(monkeypatch):
    _fake(monkeypatch, [PLANS[0]], accept=set())
    with pytest.raises(HTTPException) as e:
        await pp.create_checkout("u1", "a@b.c", "pro")
    assert e.value.status_code == 502 and "pay by card" in e.value.detail


async def test_active_plan_is_used_directly(monkeypatch):
    sent = _fake(monkeypatch, PLANS, accept={"P-OLD-PRO"})
    assert await pp.create_checkout("u1", "", "pro") == "https://paypal/approve/P-OLD-PRO"
    assert sent == ["P-OLD-PRO"]


async def test_webhook_for_fallback_plan_keeps_the_paid_tier(monkeypatch):
    from app import repository
    from app.routers import billing
    saved = {}

    async def upsert(**kw):
        saved.update(kw)

    async def plan_info(method, path, **kw):
        return {"id": "P-NEW-PRO", "name": "ProductSpy Pro — $69.99/month"}

    monkeypatch.setattr(repository, "upsert_subscription", upsert)
    monkeypatch.setattr(pp, "_request", plan_info)
    parsed = pp.parse_event({"event_type": "BILLING.SUBSCRIPTION.ACTIVATED",
                             "resource": {"id": "I-9", "plan_id": "P-NEW-PRO", "custom_id": "u9"}})
    assert parsed["plan"] is None                       # not in settings...
    await billing._apply("paypal", parsed)
    assert saved["plan"] == "pro" and saved["status"] == "active"   # ...but stored as Pro, not Free
