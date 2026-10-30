"""Email the owner when something goes wrong.

Two checks:

* After the nightly scan (winners/worker.py): one email listing every market
  that failed, hit errors, or produced fewer than MIN_PICKS picks, and the
  daily winners email if it couldn't be sent. Nothing is sent on a clean night.
* Watchdog (GET /api/v1/winners/watchdog, called by Supabase pg_cron every
  morning): emails if a market has no finished scan in the last
  WATCHDOG_HOURS — i.e. the cron job didn't run at all or crashed before
  writing anything. At most one watchdog email per day.

Recipients: ALERT_EMAILS, else ADMIN_EMAILS. Sending uses Resend, like the
other emails; without RESEND_API_KEY nothing is sent (logged instead).
An alert must never break the job, so nothing here raises.
"""
from __future__ import annotations

import html
import logging
from datetime import date, datetime, timezone
from typing import Any, Iterable

from app import config, db

log = logging.getLogger("alerts")

WATCHDOG_HOURS = 26


def recipients() -> list[str]:
    return sorted(config.ALERT_EMAILS or config.ADMIN_EMAILS)


def _page(title: str, items: Iterable[str], footer: str) -> str:
    lis = "".join(f"<li style='margin:0 0 8px'>{html.escape(i)}</li>" for i in items)
    return (f"<div style='font-family:-apple-system,Segoe UI,sans-serif;max-width:600px'>"
            f"<h2 style='margin:0 0 12px'>⚠️ {html.escape(title)}</h2><ul style='padding-left:18px'>{lis}</ul>"
            f"<p style='color:#71717a;font-size:13px'>{html.escape(footer)}</p></div>")


async def send(subject: str, items: list[str], footer: str = "") -> int:
    """Email every recipient; returns how many were sent."""
    from app.trial import send_email
    to = recipients()
    if not to:
        log.warning("alert not emailed (set ALERT_EMAILS or ADMIN_EMAILS): %s — %s", subject, items)
        return 0
    if not config.RESEND_API_KEY:
        log.warning("alert not emailed (RESEND_API_KEY missing): %s — %s", subject, items)
        return 0
    body = _page(subject, items, footer or "ProductSpy Pro · automatic alert")
    sent = 0
    for addr in to:
        try:
            sent += bool(await send_email(addr, f"[ProductSpy alert] {subject}", body))
        except Exception as exc:  # send_email never raises, but be sure
            log.warning("alert to %s failed: %s", addr, exc)
    return sent


# ── after the nightly scan ──────────────────────────────────────────────────
def scan_problems(results: list[dict], email_stats: dict | None = None, min_picks: int = 5) -> list[str]:
    """Human-readable problems from worker results ([] = clean night)."""
    out: list[str] = []
    for r in results:
        m, st, stats = r.get("market", "?"), r.get("status"), r.get("stats") or {}
        picks = sum(int(stats.get(k) or 0) for k in ("winners", "rising", "watch"))
        errs = [e for e in (r.get("errors") or []) if isinstance(e, dict)]
        if st == "failed":
            out.append(f"{m}: the scan FAILED — {_first(errs)}")
        elif errs:
            out += [f"{m}: problem in step '{e.get('step', '?')}' — {str(e.get('error', ''))[:300]}" for e in errs]
        if st != "failed" and picks < min_picks:
            out.append(f"{m}: only {picks} pick{'s' if picks != 1 else ''} today (expected at least {min_picks})")
    if email_stats:
        if email_stats.get("failed", 0) == -1:
            out.append("Daily winners email not sent: RESEND_API_KEY is missing on the cron service")
        elif email_stats.get("failed", 0) > 0:
            out.append(f"Daily winners email: {email_stats['failed']} could not be sent "
                       f"({email_stats.get('sent', 0)} sent)")
    return out


def _first(errs: list[dict]) -> str:
    return str(errs[0].get("error", "unknown error"))[:300] if errs else "unknown error"


async def after_scan(results: list[dict], email_stats: dict | None = None) -> list[str]:
    from app.winners.scoring import MIN_PICKS
    problems = scan_problems(results, email_stats, MIN_PICKS)
    if problems:
        day = datetime.now(timezone.utc).date().isoformat()
        await send(f"Nightly scan {day}: {len(problems)} problem{'s' if len(problems) != 1 else ''}", problems,
                   "Check Render → productspy-winners → Logs for details.")
    return problems


async def crashed(exc: BaseException) -> None:
    await send("Nightly scan crashed", [f"{type(exc).__name__}: {str(exc)[:500]}"],
               "The scan stopped before finishing. Check Render → productspy-winners → Logs.")


# ── watchdog: did the scan run at all? ──────────────────────────────────────
def stale_markets(runs: list[Any], markets: list[str], now: datetime, hours: int = WATCHDOG_HOURS) -> list[str]:
    """Markets with no finished run in the last `hours`."""
    last = {r["market"]: r["finished_at"] for r in runs if r["finished_at"] is not None}
    out = []
    for m in markets:
        f = last.get(m)
        if f is None:
            out.append(f"{m}: no finished scan on record")
            continue
        if f.tzinfo is None:
            f = f.replace(tzinfo=timezone.utc)
        age = (now - f).total_seconds() / 3600
        if age > hours:
            out.append(f"{m}: last finished scan was {age:.0f} hours ago")
    return out


async def watchdog() -> dict:
    from app.winners import store
    now = datetime.now(timezone.utc)
    problems = stale_markets(await store.latest_runs(), config.winners_markets(), now)
    if not problems:
        return {"ok": True}
    if not await _first_today("watchdog", now.date()):
        return {"ok": False, "emailed": False, "problems": len(problems)}
    sent = await send("The nightly scan didn't run", problems,
                      "The productspy-winners cron job may be suspended, failing to start, or missing "
                      "DATABASE_URL. Check Render → productspy-winners.")
    return {"ok": False, "emailed": bool(sent), "problems": len(problems)}


async def _first_today(kind: str, day: date) -> bool:
    """True the first time this kind of alert is raised today (so it's sent once)."""
    row = await db.fetchrow(
        "insert into alerts_sent (kind, day) values ($1, $2) on conflict do nothing returning 1", kind, day)
    return row is not None
