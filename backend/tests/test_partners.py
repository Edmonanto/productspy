"""Partner program: pure rules + routes (database stubbed). Full flow verified on Postgres."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi.testclient import TestClient

from app import db, partners
from app.auth import CurrentUser, current_user
from app.main import app

NOW = datetime(2026, 10, 29, tzinfo=timezone.utc)


def test_codes_are_normalised_and_validated():
    assert partners.clean_code(" coachMike ") == "COACHMIKE"
    assert partners.clean_code("sara-fr_2") == "SARA-FR_2"
    for bad in ("ab", "a b c", "x" * 30, "", None, "<script>"):
        assert partners.clean_code(bad) is None


def test_commission_maths():
    assert partners.commission_for(29.24, 30) == Decimal("8.77")
    assert partners.commission_for("39.00", 30) == Decimal("11.70")
    assert partners.commission_for(0, 30) == Decimal("0.00")


def test_commission_window_is_12_months_from_first_payment():
    first = NOW
    assert partners.in_commission_window(None, NOW, 12)
    assert partners.in_commission_window(first, NOW + timedelta(days=360), 12)
    assert not partners.in_commission_window(first, NOW + timedelta(days=380), 12)


def test_offer_and_admin_routes_need_the_right_user(monkeypatch):
    async def noop(*a, **k):
        return None

    async def aff(code):
        return {"code": "COACHMIKE", "name": "Coach Mike", "discount_pct": 25, "status": "active"} \
            if code.upper() == "COACHMIKE" else None
    monkeypatch.setattr(db, "connect", noop)
    monkeypatch.setattr(db, "disconnect", noop)
    monkeypatch.setattr(partners, "affiliate_by_code", aff)
    app.dependency_overrides[current_user] = lambda: CurrentUser(id="u", email="nobody@x.com", name="N", avatar_url=None)
    try:
        with TestClient(app) as c:
            assert c.get("/api/v1/partners/offer?code=coachmike").json()["discount_pct"] == 25
            assert c.get("/api/v1/partners/offer?code=nope").json() == {"valid": False}
            assert c.get("/api/v1/partners/admin").status_code == 403
            assert c.post("/api/v1/partners/admin/payouts", json={"affiliate_id": "x", "payout_ref": "r"}).status_code == 403
    finally:
        app.dependency_overrides.clear()


async def test_webhook_hooks_are_noops_without_db(monkeypatch):
    monkeypatch.setattr(db, "is_connected", lambda: False)
    assert await partners.checkout_discount("u") is None
    await partners.handle_stripe_event({"type": "invoice.paid", "data": {"object": {}}})
