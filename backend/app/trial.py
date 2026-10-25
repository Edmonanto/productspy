"""7-day free trial (no card).

* A new account's first visit writes a subscription row with status
  'trialing', plan = TRIAL_PLAN, provider 'none' (repository.ensure_subscription).
* effective_plan() decides access at read time: an app trial past its end is
  Free immediately, even before the daily job rewrites the row.
* Paying ends the trial — webhooks write provider + status 'active'.
* One trial per account (trial_used).

The daily job (`python -m app.trial`) downgrades expired trials and emails
reminders at ~2 days and ~1 day left. It runs inside the winners cron.
"""
import asyncio
import logging
import math
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

from . import config

log = logging.getLogger("trial")


def _aware(d: datetime | None) -> datetime | None:
    if d is None:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def is_app_trial(status: str | None, provider: str | None) -> bool:
    """A trial we run ourselves — not a paid subscription."""
    return status == "trialing" and (provider or "none") == "none"


def trial_active(status: str | None, provider: str | None, trial_ends_at: datetime | None,
                 now: datetime | None = None) -> bool:
    ends = _aware(trial_ends_at)
    return is_app_trial(status, provider) and ends is not None and ends > (now or datetime.now(timezone.utc))


def effective_plan(plan: str | None, status: str | None, provider: str | None,
                   trial_ends_at: datetime | None, now: datetime | None = None) -> str:
    """The plan whose features the user gets right now."""
    if is_app_trial(status, provider):
        return (plan or config.DEFAULT_PLAN) if trial_active(status, provider, trial_ends_at, now) else "free"
    if status == "canceled":
        return "free"
    return plan or config.DEFAULT_PLAN


def trial_info(row: Any, now: datetime | None = None) -> dict:
    """What the dashboard needs to show a countdown / upsell. row may be None."""
    now = now or datetime.now(timezone.utc)
    get = (lambda k: row[k] if row is not None and k in row.keys() else None) if hasattr(row, "keys") \
        else (lambda k: (row or {}).get(k))
    status, provider = get("status"), get("provider")
    ends = _aware(get("trial_ends_at"))
    used = bool(get("trial_used"))
    active = trial_active(status, provider, ends, now)
    plan_now = effective_plan(get("plan"), status, provider, ends, now) if row is not None else "free"
    secs = (ends - now).total_seconds() if (active and ends) else 0
    return {
        "active": active,
        "plan": get("plan") if active else config.TRIAL_PLAN,
        "ends_at": ends.isoformat() if ends else None,
        "days_left": math.ceil(secs / 86400) if active else 0,
        "hours_left": int(secs // 3600) if active else 0,
        "used": used,
        "expired": used and not active and plan_now == "free",
        "eligible": not used and plan_now == "free",
        "length_days": config.TRIAL_DAYS,
    }


def trial_end_from_now(now: datetime | None = None) -> datetime:
    return (now or datetime.now(timezone.utc)) + timedelta(days=config.TRIAL_DAYS)


# ── Emails ──────────────────────────────────────────────────────────────────
def _page(body: str, cta: str, path: str) -> str:
    return (
        '<div style="font-family:Inter,Arial,sans-serif;max-width:480px;margin:0 auto;'
        'padding:32px 20px;color:#18181b">'
        f"{body}"
        f'<p style="margin-top:24px"><a href="{config.APP_URL}{path}" style="background:#7c3aed;'
        'color:#fff;padding:12px 20px;border-radius:8px;text-decoration:none;font-weight:600">'
        f"{cta}</a></p></div>"
    )


def ending_email(hours_left: int) -> tuple[str, str]:
    when = "tomorrow" if hours_left > 24 else "today"
    return (
        f"Your ProductSpy Pro trial ends {when}",
        _page(
            f"<h2>Your Pro trial ends {when}</h2>"
            "<p>After that you move to the Free plan: the top 3 winning products a day, "
            "one market, no ad evidence.</p>"
            "<p>Choose a plan now to keep all 5–10 daily winners. Paying by card during "
            "the trial, you're only charged when it ends.</p>",
            "Keep Pro", "/dashboard/billing",
        ),
    )


def ended_email() -> tuple[str, str]:
    return (
        "Your ProductSpy Pro trial has ended",
        _page(
            "<h2>Your free trial has ended</h2>"
            "<p>You're on the Free plan now and still get the top 3 winners every day. "
            "The full list, extra markets, ad evidence and CSV export are on paid plans.</p>",
            "See plans", "/dashboard/billing",
        ),
    )


async def send_email(to: str | None, subject: str, html: str) -> bool:
    """Resend. Never raises — a missed email must not break the job."""
    if not (to and config.RESEND_API_KEY):
        return False
    import httpx
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {config.RESEND_API_KEY}"},
                json={"from": config.EMAIL_FROM, "to": [to], "subject": subject, "html": html},
            )
        if r.status_code >= 300:
            log.warning("email to %s failed: %s %s", to, r.status_code, r.text[:200])
            return False
        return True
    except Exception as exc:
        log.warning("email to %s failed: %s", to, exc)
        return False


async def housekeeping() -> dict[str, int]:
    """Reminders first (so a trial ending today still gets one), then expiry."""
    from . import repository

    now = datetime.now(timezone.utc)
    reminded = expired = 0
    for row in await repository.trials_due_reminder():
        ends = _aware(row["trial_ends_at"])
        hours = int((ends - now).total_seconds() // 3600) if ends else 24
        subject, html = ending_email(hours)
        await send_email(row["email"], subject, html)
        reminded += 1
    for row in await repository.expire_trials():
        subject, html = ended_email()
        await send_email(row["email"], subject, html)
        expired += 1
    return {"reminded": reminded, "expired": expired}


async def run() -> dict[str, int]:
    from . import db
    await db.connect()
    try:
        stats = await housekeeping()
        log.info("trials: %d reminded, %d expired", stats["reminded"], stats["expired"])
        return stats
    finally:
        await db.disconnect()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    try:
        asyncio.run(run())
    except Exception:
        log.exception("trial housekeeping failed")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
