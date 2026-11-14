"""Emails for quote requests.

* New request → every address in QUOTE_EMAILS (else ADMIN_EMAILS + SUPPORT_EMAIL),
  with Reply-To set to the customer so you can answer straight from your inbox.
* Admin replies → the customer gets the price and message.

Sent in the background after the response; never raises (a missed email must
not fail the request). Without RESEND_API_KEY nothing is sent, only logged.
"""
from __future__ import annotations

import html
import logging

from app import config

log = logging.getLogger("quote_emails")


def recipients() -> list[str]:
    if config.QUOTE_EMAILS:
        return sorted(config.QUOTE_EMAILS)
    from app import owner_notify
    return owner_notify.recipients()


def _money(v) -> str:
    return f"${float(v):,.2f}" if v is not None else "—"


def _rows(pairs: list[tuple[str, str]]) -> str:
    return "".join(
        f"<tr><td style='padding:6px 12px 6px 0;color:#71717a'>{html.escape(k)}</td>"
        f"<td style='padding:6px 0;color:#18181b'>{html.escape(v)}</td></tr>" for k, v in pairs)


def _wrap(title: str, table: str, extra: str, cta: str, path: str) -> str:
    return (
        "<div style='font-family:Inter,Arial,sans-serif;max-width:520px;margin:0 auto;padding:28px 20px;color:#18181b'>"
        f"<h2 style='margin:0 0 16px'>{html.escape(title)}</h2>"
        f"<table style='border-collapse:collapse;font-size:14px'>{table}</table>{extra}"
        f"<p style='margin-top:24px'><a href='{config.APP_URL}{path}' style='background:#7c3aed;color:#fff;"
        f"padding:12px 20px;border-radius:8px;text-decoration:none;font-weight:600'>{html.escape(cta)}</a></p></div>"
    )


def new_quote_email(q: dict) -> tuple[str, str]:
    subject = f"New quote request: {q['product_title']} × {q['quantity']} → {q['destination_country']}"
    table = _rows([
        ("Customer", q["user_email"]),
        ("Product", q["product_title"]),
        ("Quantity", f"{q['quantity']:,}"),
        ("Ship to", q["destination_country"]),
        ("Target price", _money(q.get("target_price_usd")) + (" / unit" if q.get("target_price_usd") else "")),
    ])
    notes = (q.get("notes") or "").strip()
    extra = (f"<p style='margin:16px 0 0;padding:12px;background:#f4f4f5;border-radius:8px;white-space:pre-wrap'>"
             f"{html.escape(notes)}</p>") if notes else ""
    extra += "<p style='color:#71717a;font-size:13px;margin-top:16px'>Reply to this email to write to the customer directly, or answer in the dashboard.</p>"
    return subject, _wrap("New quote request", table, extra, "Answer in dashboard", "/dashboard/quotes")


def reply_email(q: dict) -> tuple[str, str]:
    if q["status"] == "closed":
        subject = f"Update on your quote request: {q['product_title']}"
        table = _rows([("Product", q["product_title"]), ("Quantity", f"{q['quantity']:,}")])
    else:
        subject = f"Your quote is ready: {q['product_title']}"
        unit, ship = q.get("quoted_unit_usd"), q.get("quoted_shipping_usd")
        pairs = [("Product", q["product_title"]), ("Quantity", f"{q['quantity']:,}"),
                 ("Ship to", q["destination_country"]), ("Unit price", _money(unit))]
        if ship is not None:
            pairs.append(("Shipping / unit", _money(ship)))
        if unit is not None:
            total = (float(unit) + float(ship or 0)) * q["quantity"]
            pairs.append(("Total", _money(total)))
        table = _rows(pairs)
    msg = (q.get("reply") or "").strip()
    extra = (f"<p style='margin:16px 0 0;white-space:pre-wrap'>{html.escape(msg)}</p>") if msg else ""
    return subject, _wrap(subject.split(":")[0], table, extra, "See your quotes", "/dashboard/quotes")


async def notify_new(q: dict) -> int:
    from app.trial import send_email
    to = recipients()
    if not to:
        log.warning("quote %s not emailed: set QUOTE_EMAILS or ADMIN_EMAILS", q.get("id"))
        return 0
    if not config.RESEND_API_KEY:
        log.warning("quote %s not emailed (RESEND_API_KEY missing)", q.get("id"))
        return 0
    subject, body = new_quote_email(q)
    sent = 0
    for addr in to:
        try:
            sent += bool(await send_email(addr, subject, body, reply_to=q.get("user_email")))
        except Exception as exc:  # send_email never raises, but be sure
            log.warning("quote email to %s failed: %s", addr, exc)
    return sent


async def notify_customer(q: dict) -> bool:
    from app.trial import send_email
    try:
        subject, body = reply_email(q)
        return bool(await send_email(q.get("user_email"), subject, body))
    except Exception as exc:
        log.warning("quote reply email failed: %s", exc)
        return False
