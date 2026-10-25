"""Daily winners email — sent once the morning scan has finished.

    python -m app.winners.digest                 # everyone who gets it (skips anyone already sent today)
    python -m app.winners.digest --to me@x.com   # just this address: full picks, every live market (testing)

Who gets what:
  * ADMIN_EMAILS — every pick of every live market, every day.
  * Users with the daily email switched on (Settings; on by default) — the
    picks of the markets they follow, cut to what their plan includes
    (Free: top 3 of one market). Never more than one email a day.

Every email carries a signed one-click unsubscribe link (no login needed).
Sending uses Resend (RESEND_API_KEY); without it nothing is sent and the run
says so.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import html
import json
import logging
import sys
from datetime import date, datetime, timezone
from typing import Any

from app import config, db
from app.trial import effective_plan, send_email

from . import store
from .markets import MARKETS

log = logging.getLogger("winners.digest")


# ── unsubscribe links ───────────────────────────────────────────────────────
def _secret() -> bytes:
    raw = config.DIGEST_SECRET or config.SUPABASE_JWT_SECRET or config.DATABASE_URL or "productspy"
    return hashlib.sha256(("digest:" + raw).encode()).digest()


def unsubscribe_token(user_id: str) -> str:
    return hmac.new(_secret(), user_id.encode(), hashlib.sha256).hexdigest()[:32]


def valid_token(user_id: str, token: str) -> bool:
    return hmac.compare_digest(unsubscribe_token(user_id), token or "")


def unsubscribe_url(user_id: str) -> str:
    return f"{config.API_PUBLIC_URL}/winners/digest/unsubscribe?u={user_id}&t={unsubscribe_token(user_id)}"


# ── content ─────────────────────────────────────────────────────────────────
def _live() -> list[str]:
    return [c for c in config.winners_markets() if c in MARKETS]


def _money(v: Any) -> str:
    return f"${float(v):,.2f}" if v is not None else "—"


def _reasons(raw: Any) -> list[str]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return []
    return [str(r) for r in (raw or [])][:2]


TIER = {"winner": ("Winner", "#047857", "#d1fae5"), "rising": ("Rising", "#b45309", "#fef3c7"),
        "watch": ("Watch", "#0369a1", "#e0f2fe")}


def _pick_html(r: Any, market: str) -> str:
    e = html.escape
    label, fg, bg = TIER.get(r["tier"], TIER["watch"])
    price, cost = r["price_usd"], r["cost_usd"]
    markup = f' · <span style="color:#047857">{float(price) / float(cost):.1f}× cost</span>' \
        if price and cost else ""
    reasons = "".join(f'<li style="margin:2px 0">{e(x)}</li>' for x in _reasons(r["reasons"]))
    link = f'{config.APP_URL}/dashboard/winners/{r["product_id"]}?market={market}'
    return (
        '<tr><td style="padding:14px 0;border-top:1px solid #e4e4e7">'
        f'<div style="font-size:12px;color:#71717a">#{r["rank"]} '
        f'<span style="background:{bg};color:{fg};border-radius:4px;padding:1px 6px;font-weight:600">{label}</span> '
        f'score <b style="color:#18181b">{r["total"]}</b>/100</div>'
        f'<div style="font-size:16px;font-weight:600;margin:4px 0">'
        f'<a href="{link}" style="color:#18181b;text-decoration:none">{e(r["title"])}</a></div>'
        f'<div style="font-size:13px;color:#3f3f46">Sells {_money(price)}{markup}</div>'
        f'<ul style="font-size:13px;color:#52525b;margin:6px 0 0;padding-left:18px">{reasons}</ul>'
        f'<div style="margin-top:8px"><a href="{link}" style="font-size:13px;color:#6d28d9;font-weight:600">'
        'See the ads and evidence</a></div>'
        '</td></tr>'
    )


def build_email(sections: list[tuple[str, list[Any]]], day: date, unsubscribe: str | None) -> tuple[str, str]:
    """sections = [(market code, pick rows)]. Returns (subject, html)."""
    total = sum(len(rows) for _, rows in sections)
    winners = sum(1 for _, rows in sections for r in rows if r["tier"] == "winner")
    names = ", ".join(MARKETS[c].name for c, rows in sections if rows) or "your markets"
    nice_day = day.strftime("%A %d %B").replace(" 0", " ")
    subject = (f"{winners} winning product{'s' if winners != 1 else ''} today — {names}" if winners
               else f"Today's {total} products to watch — {names}" if total
               else f"No new picks today — {names}")
    blocks = []
    for code, rows in sections:
        m = MARKETS[code]
        body = "".join(_pick_html(r, code) for r in rows) or (
            '<tr><td style="padding:12px 0;border-top:1px solid #e4e4e7;font-size:13px;color:#71717a">'
            "No product passed the bar in this market today.</td></tr>")
        blocks.append(
            f'<h2 style="font-size:18px;margin:28px 0 4px">{m.flag} {html.escape(m.name)}</h2>'
            f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0">{body}</table>'
        )
    footer = (f'<p style="font-size:12px;color:#a1a1aa;margin-top:28px">You get this because the daily '
              f'winners email is on for your ProductSpy Pro account. '
              f'<a href="{unsubscribe}" style="color:#a1a1aa">Unsubscribe</a> · '
              f'<a href="{config.APP_URL}/dashboard/settings" style="color:#a1a1aa">Email settings</a></p>'
              if unsubscribe else
              '<p style="font-size:12px;color:#a1a1aa;margin-top:28px">Admin copy: every pick of every live market.</p>')
    page = (
        '<div style="font-family:Inter,Arial,sans-serif;max-width:560px;margin:0 auto;padding:28px 20px;color:#18181b">'
        f'<div style="font-size:13px;color:#7c3aed;font-weight:700">ProductSpy Pro</div>'
        f'<h1 style="font-size:22px;margin:6px 0 2px">Daily winners · {nice_day}</h1>'
        f'<p style="font-size:14px;color:#52525b;margin:0">{winners} winner{"s" if winners != 1 else ""}, '
        f'{total} products in total. Scores of 70+ are winners; 60–69 rising; below that, early signals.</p>'
        + "".join(blocks) +
        f'<p style="margin-top:24px"><a href="{config.APP_URL}/dashboard/winners" style="background:#7c3aed;'
        'color:#fff;padding:12px 20px;border-radius:8px;text-decoration:none;font-weight:600">'
        'Open Daily Winners</a></p>' + footer + '</div>'
    )
    return subject, page


# ── recipients ──────────────────────────────────────────────────────────────
async def recipients() -> list[dict]:
    rows = await db.fetch(
        """
        select s.user_id, s.email, s.plan, s.status, s.provider, s.trial_ends_at,
               coalesce(p.markets, array['US']) as markets,
               coalesce(p.email_digest, true) as email_digest, p.digest_sent_on
          from subscriptions s
          left join user_preferences p on p.user_id = s.user_id
         where s.email is not null and s.email <> ''
        """
    )
    return [dict(r) for r in rows]


async def mark_sent(user_id: str, day: date) -> None:
    await db.execute(
        """
        insert into user_preferences (user_id, digest_sent_on, updated_at) values ($1, $2, now())
        on conflict (user_id) do update set digest_sent_on = excluded.digest_sent_on
        """,
        user_id, day,
    )


async def set_digest(user_id: str, on: bool) -> None:
    await db.execute(
        """
        insert into user_preferences (user_id, email_digest, updated_at) values ($1, $2, now())
        on conflict (user_id) do update set email_digest = excluded.email_digest, updated_at = now()
        """,
        user_id, on,
    )


async def get_digest(user_id: str) -> bool:
    v = await db.fetchval("select email_digest from user_preferences where user_id = $1", user_id)
    return True if v is None else bool(v)


async def _picks_by_market(day: date) -> dict[str, list[Any]]:
    return {code: list(await store.picks(code, day)) for code in _live()}


def _user_sections(u: dict, picks: dict[str, list[Any]]) -> list[tuple[str, list[Any]]]:
    plan = effective_plan(u["plan"], u["status"], u["provider"], u["trial_ends_at"])
    ent = config.WINNERS_PLANS.get(plan, config.WINNERS_PLANS["free"])
    followed = [c for c in (u["markets"] or []) if c in picks][: ent["markets"]] or _live()[:1]
    return [(c, picks[c][: ent["winners_per_day"]]) for c in followed]


async def send_all(day: date | None = None, only_to: str | None = None) -> dict[str, int]:
    day = day or datetime.now(timezone.utc).date()
    stats = {"sent": 0, "skipped": 0, "failed": 0}
    if not config.RESEND_API_KEY:
        log.warning("RESEND_API_KEY is not set — no daily emails sent")
        stats["failed"] = -1
        return stats
    picks = await _picks_by_market(day)
    everything = [(c, rows) for c, rows in picks.items()]

    if only_to:
        subject, page = build_email(everything, day, None)
        ok = await send_email(only_to, subject, page)
        stats["sent" if ok else "failed"] += 1
        return stats

    admins = set(config.ADMIN_EMAILS)
    done: set[str] = set()
    for u in await recipients():
        email = (u["email"] or "").lower()
        if email in done:
            continue
        is_admin = email in admins
        if not is_admin and not u["email_digest"]:
            stats["skipped"] += 1
            continue
        if u["digest_sent_on"] == day:
            stats["skipped"] += 1
            continue
        sections = everything if is_admin else _user_sections(u, picks)
        if not is_admin and not any(rows for _, rows in sections):
            stats["skipped"] += 1          # nothing to show them today
            continue
        subject, page = build_email(sections, day, None if is_admin else unsubscribe_url(str(u["user_id"])))
        if await send_email(u["email"], subject, page):
            await mark_sent(str(u["user_id"]), day)
            stats["sent"] += 1
        else:
            stats["failed"] += 1
        done.add(email)

    # Admins who have no account row still get their copy.
    for email in admins - done:
        subject, page = build_email(everything, day, None)
        stats["sent" if await send_email(email, subject, page) else "failed"] += 1
    return stats


async def _run(only_to: str | None) -> dict[str, int]:
    await db.connect()
    try:
        return await send_all(only_to=only_to)
    finally:
        await db.disconnect()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--to", default="", help="send only to this address (full admin copy) — for testing")
    args = ap.parse_args()
    stats = asyncio.run(_run(args.to.strip() or None))
    log.info("daily email: %s", stats)
    return 0 if stats["failed"] >= 0 else 1


if __name__ == "__main__":
    sys.exit(main())
