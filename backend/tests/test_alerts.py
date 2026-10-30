"""Failure emails: what counts as a problem, who gets it, and the watchdog."""
from datetime import datetime, timedelta, timezone

from app import alerts, config

NOW = datetime(2026, 10, 31, 3, 30, tzinfo=timezone.utc)


def ok(m, picks=6):
    return {"market": m, "status": "ok", "stats": {"winners": 2, "rising": picks - 2}, "errors": []}


def test_clean_night_has_no_problems():
    assert alerts.scan_problems([ok("US"), ok("UK"), ok("FR")], {"sent": 3, "failed": 0}) == []


def test_failed_partial_thin_and_email():
    results = [
        {"market": "US", "status": "failed", "stats": {}, "errors": [{"step": "pipeline", "error": "DATABASE_URL is not set"}]},
        {"market": "UK", "status": "partial", "stats": {"winners": 5},
         "errors": [{"step": "google_trends", "error": "Apify 402 not enough credit"}]},
        ok("FR", picks=3),
    ]
    p = alerts.scan_problems(results, {"sent": 0, "failed": -1})
    assert p[0] == "US: the scan FAILED — DATABASE_URL is not set"
    assert "UK: problem in step 'google_trends' — Apify 402 not enough credit" in p
    assert "FR: only 3 picks today (expected at least 5)" in p
    assert any("RESEND_API_KEY is missing" in x for x in p)
    assert not any(x.startswith("US: only") for x in p)      # a failed market isn't also "thin"


def test_recipients_fall_back_to_admins(monkeypatch):
    monkeypatch.setattr(config, "ALERT_EMAILS", set())
    monkeypatch.setattr(config, "ADMIN_EMAILS", {"owner@x.com"})
    assert alerts.recipients() == ["owner@x.com"]
    monkeypatch.setattr(config, "ALERT_EMAILS", {"alerts@x.com"})
    assert alerts.recipients() == ["alerts@x.com"]


async def test_send_emails_each_recipient(monkeypatch):
    sent = []

    async def fake(to, subject, html):
        sent.append((to, subject, html))
        return True
    import app.trial
    monkeypatch.setattr(app.trial, "send_email", fake)
    monkeypatch.setattr(config, "ALERT_EMAILS", {"a@x.com", "b@x.com"})
    monkeypatch.setattr(config, "RESEND_API_KEY", "re_test")
    n = await alerts.send("Nightly scan: 1 problem", ["US: <b>bad</b>"])
    assert n == 2 and sent[0][1] == "[ProductSpy alert] Nightly scan: 1 problem"
    assert "&lt;b&gt;bad&lt;/b&gt;" in sent[0][2]                    # escaped


async def test_send_without_key_or_recipients_is_quiet(monkeypatch):
    monkeypatch.setattr(config, "ALERT_EMAILS", set())
    monkeypatch.setattr(config, "ADMIN_EMAILS", set())
    assert await alerts.send("x", ["y"]) == 0
    monkeypatch.setattr(config, "ALERT_EMAILS", {"a@x.com"})
    monkeypatch.setattr(config, "RESEND_API_KEY", "")
    assert await alerts.send("x", ["y"]) == 0


def test_stale_markets():
    runs = [{"market": "US", "finished_at": NOW - timedelta(hours=2)},
            {"market": "UK", "finished_at": NOW - timedelta(hours=50)},
            {"market": "FR", "finished_at": None}]
    out = alerts.stale_markets(runs, ["US", "UK", "FR", "DE"], NOW)
    assert out == ["UK: last finished scan was 50 hours ago", "FR: no finished scan on record",
                   "DE: no finished scan on record"]


async def test_watchdog_emails_once(monkeypatch):
    from app.winners import store

    async def runs():
        return [{"market": "US", "finished_at": NOW - timedelta(hours=40)}]
    calls = []

    async def send(subject, items, footer=""):
        calls.append(subject)
        return 1
    first = iter([True, False])

    async def first_today(kind, day):
        return next(first)
    monkeypatch.setattr(store, "latest_runs", runs)
    monkeypatch.setattr(config, "winners_markets", lambda: ["US"])
    monkeypatch.setattr(alerts, "send", send)
    monkeypatch.setattr(alerts, "_first_today", first_today)
    assert (await alerts.watchdog())["emailed"] is True
    assert (await alerts.watchdog())["emailed"] is False
    assert calls == ["The nightly scan didn't run"]
