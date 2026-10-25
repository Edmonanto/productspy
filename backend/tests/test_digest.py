"""Daily winners email: content, who gets what, unsubscribe."""
from datetime import date, datetime, timedelta, timezone

import pytest

from app import config
from app.winners import digest

DAY = date(2026, 10, 26)


def pick(rank, tier="winner", total=80, title="Posture Corrector"):
    return {"rank": rank, "tier": tier, "total": total, "title": title, "product_id": f"p{rank}",
            "price_usd": 34.99, "cost_usd": 6.2, "reasons": '["Ad running 41 days", "5 stores", "third"]'}


def test_email_lists_picks_with_links_and_reasons():
    subject, page = digest.build_email([("US", [pick(1), pick(2, "rising", 64, "LED <Mirror>")]), ("FR", [])],
                                       DAY, "https://x/unsub")
    assert subject.startswith("1 winning product today")
    assert "United States" in subject and "France" not in subject.split("—")[1]
    assert "/dashboard/winners/p1?market=US" in page and "5.6× cost" in page
    assert "Ad running 41 days" in page and "third" not in page          # top 2 reasons only
    assert "LED &lt;Mirror&gt;" in page                                   # escaped
    assert "No product passed the bar" in page                            # empty FR section
    assert "https://x/unsub" in page


def test_unsubscribe_token_is_signed():
    uid = "11111111-1111-1111-1111-111111111111"
    t = digest.unsubscribe_token(uid)
    assert digest.valid_token(uid, t)
    assert not digest.valid_token(uid, t[:-1] + ("0" if t[-1] != "0" else "1"))
    assert not digest.valid_token("22222222-2222-2222-2222-222222222222", t)


async def test_who_gets_what(monkeypatch):
    monkeypatch.setattr(config, "RESEND_API_KEY", "re_test")
    monkeypatch.setattr(config, "WINNERS_MARKETS", "US,UK,FR")
    monkeypatch.setattr(config, "ADMIN_EMAILS", {"boss@x.com"})
    future = datetime.now(timezone.utc) + timedelta(days=3)
    users = [
        # admin: everything, even with the email switched off
        {"user_id": "a", "email": "Boss@x.com", "plan": "free", "status": "active", "provider": "none",
         "trial_ends_at": None, "markets": ["US"], "email_digest": False, "digest_sent_on": None},
        # free user: top 3 of one market
        {"user_id": "b", "email": "free@x.com", "plan": "free", "status": "active", "provider": "stripe",
         "trial_ends_at": None, "markets": ["UK", "US"], "email_digest": True, "digest_sent_on": None},
        # pro trial: followed markets, all picks
        {"user_id": "c", "email": "pro@x.com", "plan": "pro", "status": "trialing", "provider": "none",
         "trial_ends_at": future, "markets": ["US", "FR"], "email_digest": True, "digest_sent_on": None},
        # switched off
        {"user_id": "d", "email": "off@x.com", "plan": "pro", "status": "active", "provider": "stripe",
         "trial_ends_at": None, "markets": ["US"], "email_digest": False, "digest_sent_on": None},
        # already sent today
        {"user_id": "e", "email": "done@x.com", "plan": "pro", "status": "active", "provider": "stripe",
         "trial_ends_at": None, "markets": ["US"], "email_digest": True, "digest_sent_on": DAY},
    ]
    picks = {"US": [pick(i) for i in range(1, 7)], "UK": [pick(i) for i in range(1, 6)], "FR": [pick(1)]}
    sent, marked = [], []

    async def fake_recipients(): return users
    async def fake_picks(day): return picks
    async def fake_send(to, subject, page): sent.append((to, subject, page)); return True
    async def fake_mark(uid, day): marked.append(uid)

    monkeypatch.setattr(digest, "recipients", fake_recipients)
    monkeypatch.setattr(digest, "_picks_by_market", fake_picks)
    monkeypatch.setattr(digest, "send_email", fake_send)
    monkeypatch.setattr(digest, "mark_sent", fake_mark)

    stats = await digest.send_all(DAY)
    by = {to.lower(): page for to, _, page in sent}
    assert set(by) == {"boss@x.com", "free@x.com", "pro@x.com"}
    assert stats == {"sent": 3, "skipped": 2, "failed": 0}
    assert by["boss@x.com"].count("/dashboard/winners/p") >= 12 and "Unsubscribe" not in by["boss@x.com"]
    free = by["free@x.com"]
    assert "United Kingdom" in free and "United States" not in free and free.count("See the ads") == 3
    assert "United States" in by["pro@x.com"] and "France" in by["pro@x.com"]
    assert "Unsubscribe" in by["pro@x.com"]
    assert set(marked) == {"a", "b", "c"}


async def test_no_key_sends_nothing(monkeypatch):
    monkeypatch.setattr(config, "RESEND_API_KEY", "")
    assert (await digest.send_all(DAY))["failed"] == -1
