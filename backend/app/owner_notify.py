"""Emails to the owner: new signups, new paid subscriptions, and a daily report.

* notify_signup       — a brand-new account (first dashboard visit).
* notify_subscription — a user moves onto a paid plan (not on renewals).
* daily_report        — after the nightly scan: Apify credits used per day and
                        this billing cycle vs. APIFY_MONTHLY_BUDGET_USD, plus
                        signups and new paid customers in the last 24 hours.

Recipients: NOTIFY_EMAILS, else ADMIN_EMAILS + SUPPORT_EMAIL. Sent with Resend;
without RESEND_API_KEY nothing is sent (logged). Nothing here ever raises.
"""
from __future__ import annotations

import html
import logging
from datetime import datetime, timezone

from app import config, db

log = logging.getLogger("owner_notify")


def recipients() -> list[str]:
    if config.NOTIFY_EMAILS:
        return sorted(config.NOTIFY_EMAILS)
    out = set(config.ADMIN_EMAILS)
    if config.SUPPORT_EMAIL:
        out.add(config.SUPPORT_EMAIL.lower())
    return sorted(out)


def page(title: str, rows: list[tuple[str, str]], extra: str = "") -> str:
    trs = "".join(
        f"<tr><td style='padding:6px 14px 6px 0;color:#71717a'>{html.escape(k)}</td>"
        f"<td style='padding:6px 0;color:#18181b'>{html.escape(v)}</td></tr>" for k, v in rows)
    return ("<div style='font-family:Inter,Arial,sans-serif;max-width:560px;margin:0 auto;padding:24px 20px;color:#18181b'>"
            f"<h2 style='margin:0 0 14px'>{html.escape(title)}</h2>"
            f"<table style='border-collapse:collapse;font-size:14px'>{trs}</table>{extra}"
            "<p style='color:#a1a1aa;font-size:12px;margin-top:20px'>ProductSpy Pro · owner notification</p></div>")


async def send(subject: str, body: str, reply_to: str | None = None) -> int:
    from app.trial import send_email
    to = recipients()
    if not to or not config.RESEND_API_KEY:
        log.warning("owner email not sent (%s): %s", "no recipients" if not to else "RESEND_API_KEY missing", subject)
        return 0
    sent = 0
    for addr in to:
        try:
            sent += bool(await send_email(addr, subject, body, reply_to=reply_to))
        except Exception as exc:  # send_email never raises, but be sure
            log.warning("owner email to %s failed: %s", addr, exc)
    return sent


# ── signups and subscriptions ───────────────────────────────────────────────
async def notify_signup(email: str | None, name: str | None = None, lang: str | None = None) -> int:
    rows = [("Email", email or "?"), ("Name", name or "—"), ("Language", (lang or "en").upper()),
            ("Plan", f"free trial ({config.TRIAL_PLAN}, {config.TRIAL_DAYS} days)")]
    return await send(f"New signup: {email or 'unknown'}", page("New signup", rows), reply_to=email)


def is_paid(plan: str | None, status: str | None) -> bool:
    return plan in config.PAID_PLANS and status in ("active", "trialing")


async def notify_subscription(email: str | None, plan: str, provider: str, status: str,
                              previous_plan: str | None = None) -> int:
    kind = "Upgrade" if previous_plan in config.PAID_PLANS else "New subscriber"
    rows = [("Email", email or "?"), ("Plan", plan), ("Paid with", provider.title()), ("Status", status)]
    if previous_plan and previous_plan != plan:
        rows.append(("Before", previous_plan))
    return await send(f"💰 {kind}: {email or 'unknown'} → {plan}", page(kind, rows), reply_to=email)


# ── daily report ────────────────────────────────────────────────────────────
async def apify_usage() -> dict | None:
    """{"days": [(date, usd)], "cycle_usd", "cycle_end"} from Apify, or None."""
    if not config.APIFY_TOKEN:
        return None
    import httpx
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get("https://api.apify.com/v2/users/me/usage/monthly",
                                 headers={"Authorization": f"Bearer {config.APIFY_TOKEN}"})
        if r.status_code >= 300:
            log.warning("apify usage: %s %s", r.status_code, r.text[:200])
            return None
        d = r.json().get("data") or {}
    except Exception as exc:
        log.warning("apify usage failed: %s", exc)
        return None
    days = [(str(x.get("date", ""))[:10], float(x.get("totalUsageCreditsUsd") or 0))
            for x in d.get("dailyServiceUsages") or []]
    return {"days": days, "cycle_usd": sum(u for _, u in days),
            "cycle_end": str((d.get("usageCycle") or {}).get("endAt") or "")[:10]}


async def _people_last_day() -> tuple[list[str], list[str]]:
    """(signup emails, new paid emails) in the last 24 hours, from funnel_events."""
    if not db.is_connected():
        return [], []
    try:
        rows = await db.fetch(
            """
            select f.event, coalesce(s.email, f.user_id::text) as who, f.source
              from funnel_events f left join subscriptions s on s.user_id = f.user_id
             where f.event in ('account_created', 'paid') and f.created_at >= now() - interval '24 hours'
             order by f.created_at
            """)
    except Exception as exc:
        log.warning("daily report people failed: %s", exc)
        return [], []
    signups = [r["who"] for r in rows if r["event"] == "account_created"]
    paid = [f"{r['who']} ({r['source']})" if r["source"] else r["who"] for r in rows if r["event"] == "paid"]
    return signups, list(dict.fromkeys(paid))


def report_email(usage: dict | None, signups: list[str], paid: list[str], today: str) -> tuple[str, str]:
    budget = config.APIFY_MONTHLY_BUDGET_USD
    rows: list[tuple[str, str]] = []
    extra = ""
    if usage:
        by_day = dict(usage["days"])
        recent = sorted(by_day.items())[-7:]
        from datetime import date, timedelta
        yesterday = by_day.get((date.fromisoformat(today) - timedelta(days=1)).isoformat(), 0.0)
        today_usd = by_day.get(today, 0.0)
        rows += [("Apify yesterday", f"${yesterday:.2f}"), ("Apify today so far", f"${today_usd:.2f}"),
                 ("This billing cycle", f"${usage['cycle_usd']:.2f}" + (f" of ${budget:.0f}" if budget else "")),
                 ("Cycle resets", usage["cycle_end"] or "?")]
        if budget and usage["cycle_usd"] >= budget * 0.8:
            extra += (f"<p style='color:#b45309'>⚠️ {usage['cycle_usd'] / budget * 100:.0f}% of the monthly "
                      "Apify budget is used. Scraping stops at 100% until the cycle resets.</p>")
        extra += ("<p style='margin:16px 0 6px;font-weight:600'>Apify credits per day</p>"
                  "<table style='border-collapse:collapse;font-size:13px'>" + "".join(
                      f"<tr><td style='padding:3px 14px 3px 0;color:#71717a'>{d}</td><td>${u:.2f}</td></tr>"
                      for d, u in reversed(recent)) + "</table>")
        head = f"Apify ${yesterday:.2f} yesterday · ${usage['cycle_usd']:.2f}" + (f"/${budget:.0f}" if budget else "")
    else:
        rows.append(("Apify", "usage could not be read (check APIFY_TOKEN)"))
        head = "Apify usage unavailable"
    rows += [("New signups (24h)", str(len(signups))), ("New paid (24h)", str(len(paid)))]
    if signups or paid:
        extra += ("<p style='margin:16px 0 6px;font-weight:600'>Last 24 hours</p><ul style='padding-left:18px;margin:0'>"
                  + "".join(f"<li>Signup: {html.escape(e)}</li>" for e in signups)
                  + "".join(f"<li>Paid: {html.escape(e)}</li>" for e in paid) + "</ul>")
    subject = f"ProductSpy daily: {head} · {len(signups)} signup{'s' if len(signups) != 1 else ''}"
    return subject, page(f"Daily report — {today}", rows, extra)


async def daily_report() -> int:
    try:
        today = datetime.now(timezone.utc).date().isoformat()
        usage = await apify_usage()
        signups, paid = await _people_last_day()
        subject, body = report_email(usage, signups, paid, today)
        return await send(subject, body)
    except Exception as exc:
        log.warning("daily report failed: %s", exc)
        return 0
