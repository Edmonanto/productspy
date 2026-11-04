"""Signup funnel: anonymous landing events, once-per-user milestones, admin summary."""
import pytest
from fastapi.testclient import TestClient

from app import config, db, funnel, repository
from app.auth import CurrentUser, current_user
from app.main import app
from app.routers import billing, events

USER = CurrentUser(id="11111111-1111-1111-1111-111111111111", email="boss@x.com",
                   name="Boss", avatar_url=None, locale="fr")


@pytest.fixture
def recorded(monkeypatch):
    calls: list[tuple] = []

    async def record(event, *, user_id=None, lang=None, source=None):
        calls.append((event, user_id, lang, source))

    monkeypatch.setattr(funnel, "record", record)
    events._hits.clear()
    return calls


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(db, "connect", lambda: _none())
    monkeypatch.setattr(db, "disconnect", lambda: _none())
    app.dependency_overrides[current_user] = lambda: USER
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


async def _none(*_a, **_k):
    return None


def test_landing_events_are_recorded_anonymously(client, recorded):
    # sendBeacon posts text/plain
    r = client.post("/api/v1/events", content='{"event":"signup_click","lang":"fr","source":"hero"}',
                    headers={"content-type": "text/plain"})
    assert r.status_code == 204
    assert recorded == [("signup_click", None, "fr", "hero")]


def test_unknown_or_user_events_are_refused(client, recorded):
    for body in ('{"event":"paid"}', '{"event":"account_created"}', "not json", "[]"):
        assert client.post("/api/v1/events", content=body).status_code == 400
    assert recorded == []


def test_anonymous_events_are_rate_limited(client, recorded):
    for _ in range(events.RATE_PER_MINUTE + 5):
        assert client.post("/api/v1/events", content='{"event":"landing_view","lang":"en"}').status_code == 204
    assert len(recorded) == events.RATE_PER_MINUTE


def test_funnel_summary_is_admin_only(client, monkeypatch):
    async def summary(days):
        return {"days": days, "steps": [], "signup_click_sources": []}

    monkeypatch.setattr(funnel, "summary", summary)
    monkeypatch.setattr(config, "ADMIN_EMAILS", set())
    assert client.get("/api/v1/events/funnel").status_code == 403
    monkeypatch.setattr(config, "ADMIN_EMAILS", {"boss@x.com"})
    assert client.get("/api/v1/events/funnel?days=7").json()["days"] == 7


def test_account_created_only_on_first_visit(client, recorded, monkeypatch):
    from app.schemas import Subscription
    state = {"new": True}

    async def ensure(_uid, _email):
        was, state["new"] = state["new"], False
        return was

    async def sub(_uid):
        return Subscription(plan="pro", status="trialing", current_period_end=None), "none"

    monkeypatch.setattr(repository, "ensure_subscription", ensure)
    monkeypatch.setattr(repository, "subscription", sub)
    monkeypatch.setattr(repository, "subscription_row", _none)
    client.get("/api/v1/users/me")
    client.get("/api/v1/users/me")
    assert recorded == [("account_created", USER.id, "fr", None)]


async def test_paid_recorded_from_webhook_only_for_paid_plans(recorded, monkeypatch):
    monkeypatch.setattr(repository, "upsert_subscription", _none)
    await billing._apply("stripe", {"user_id": "u1", "plan": "pro", "status": "trialing"})
    await billing._apply("stripe", {"user_id": "u2", "plan": "pro", "status": "canceled"})
    await billing._apply("stripe", {"user_id": "u3", "plan": "free", "status": "active"})
    assert recorded == [("paid", "u1", None, "pro")]


async def test_record_never_raises(monkeypatch):
    async def boom(*_a):
        raise RuntimeError("db down")

    monkeypatch.setattr(db, "is_connected", lambda: True)
    monkeypatch.setattr(db, "execute", boom)
    await funnel.record("landing_view", lang="fr")  # logged, not raised
    await funnel.record("not_an_event")             # ignored


def test_clean_lang():
    assert funnel.clean_lang("fr-FR") == "fr" and funnel.clean_lang("de") is None and funnel.clean_lang(None) is None
