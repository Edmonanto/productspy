"""Coach / partner referral program — attribution, discount, commissions.

  * attribution: first touch, within ATTRIBUTION_DAYS of the account being
    created, never the partner's own account, never someone already paying.
  * discount: the partner's discount_pct off the FIRST paid month (Stripe
    coupon, duration "once"), applied automatically at checkout.
  * commission: commission_pct of every paid invoice (excluding tax) for
    commission_months after the customer's first payment. A refund voids it.
    Commissions become payable after HOLD_DAYS (refund window).

Money is only ever recorded from verified payment webhooks.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Optional

from . import config, db

log = logging.getLogger("partners")

ATTRIBUTION_DAYS = 30
HOLD_DAYS = 14
CODE_RX = re.compile(r"^[A-Z0-9][A-Z0-9_-]{2,23}$")


def clean_code(code: str | None) -> Optional[str]:
    c = (code or "").strip().upper()
    return c if CODE_RX.match(c) else None


def money(x: Any) -> Decimal:
    return Decimal(str(x or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def commission_for(amount: Any, pct: Any) -> Decimal:
    return money(Decimal(str(amount or 0)) * Decimal(str(pct or 0)) / Decimal(100))


def in_commission_window(first_paid_at: Optional[datetime], paid_at: datetime, months: int) -> bool:
    if first_paid_at is None:
        return True                       # this IS the first payment
    return paid_at <= first_paid_at + timedelta(days=round(30.44 * months))


# ── lookups ──────────────────────────────────────────────────────────────────
async def affiliate_by_code(code: str) -> Optional[dict]:
    c = clean_code(code)
    if not c:
        return None
    row = await db.fetchrow("select * from affiliates where code = $1", c)
    return dict(row) if row else None


async def affiliate_for_user(user_id: str, email: str) -> Optional[dict]:
    """The partner record of this user — linked by id, or by email the first time."""
    row = await db.fetchrow("select * from affiliates where user_id = $1", user_id)
    if not row and email:
        row = await db.fetchrow(
            "update affiliates set user_id = $1 where user_id is null and lower(email) = lower($2) returning *",
            user_id, email)
    return dict(row) if row else None


async def referral_of(user_id: str) -> Optional[dict]:
    row = await db.fetchrow(
        "select r.*, a.name, a.discount_pct, a.commission_pct, a.commission_months, a.status as a_status, "
        "a.email as a_email, a.user_id as a_user from referrals r join affiliates a on a.id = r.affiliate_id "
        "where r.user_id = $1", user_id)
    return dict(row) if row else None


# ── attribution ──────────────────────────────────────────────────────────────
async def record_click(code: str) -> bool:
    c = clean_code(code)
    if not c:
        return False
    return (await db.execute("update affiliates set clicks = clicks + 1 where code = $1 and status = 'active'", c)
            ).endswith("1")


async def attribute(user_id: str, email: str, code: str) -> tuple[bool, str]:
    """Link a new customer to a partner. Returns (ok, reason)."""
    aff = await affiliate_by_code(code)
    if not aff or aff["status"] != "active":
        return False, "unknown or inactive code"
    if await referral_of(user_id):
        return False, "already referred"
    if str(aff.get("user_id") or "") == str(user_id) or (email and aff["email"].lower() == email.lower()):
        return False, "partners can't refer themselves"
    # The free trial starts at signup, so trial_started_at is the account's age.
    sub = await db.fetchrow("select trial_started_at as created_at, provider, status from subscriptions "
                            "where user_id = $1", user_id)
    if sub:
        created = sub["created_at"]
        if created and created < datetime.now(timezone.utc) - timedelta(days=ATTRIBUTION_DAYS):
            return False, "account older than the referral window"
        if sub["provider"] in ("stripe", "paypal") and sub["status"] == "active":
            return False, "already a paying customer"
    await db.execute(
        "insert into referrals (user_id, affiliate_id, code) values ($1, $2, $3) on conflict do nothing",
        user_id, aff["id"], aff["code"])
    return True, "ok"


# ── discount at checkout ─────────────────────────────────────────────────────
_coupon_cache: dict[str, str] = {}


def ensure_coupon(stripe: Any, pct: Any) -> str:
    """One Stripe coupon per discount level, reused (id productspy-partner-<pct>)."""
    pct_i = int(Decimal(str(pct)))
    cid = f"productspy-partner-{pct_i}"
    if cid in _coupon_cache:
        return cid
    try:
        stripe.Coupon.retrieve(cid)
    except Exception:
        stripe.Coupon.create(id=cid, percent_off=pct_i, duration="once",
                             name=f"Partner discount {pct_i}% (first month)")
    _coupon_cache[cid] = cid
    return cid


async def checkout_discount(user_id: str) -> Optional[Decimal]:
    """Discount % for this user's first paid month, or None."""
    if not db.is_connected():
        return None
    r = await referral_of(user_id)
    if not r or r["first_paid_at"] is not None or r["a_status"] != "active" or not r["discount_pct"]:
        return None
    return Decimal(str(r["discount_pct"]))


# ── commissions (from verified webhooks) ─────────────────────────────────────
async def record_payment(provider: str, user_id: Optional[str], invoice_id: str, amount: Any,
                         currency: str, paid_at: Optional[datetime] = None) -> Optional[Decimal]:
    """A referred customer paid: store the commission (idempotent per invoice)."""
    if not user_id or not invoice_id or money(amount) <= 0:
        return None
    r = await referral_of(user_id)
    if not r:
        return None
    paid_at = paid_at or datetime.now(timezone.utc)
    if not in_commission_window(r["first_paid_at"], paid_at, int(r["commission_months"])):
        return None
    com = commission_for(amount, r["commission_pct"])
    inserted = await db.fetchval(
        """
        insert into commissions (affiliate_id, user_id, provider, invoice_id, amount, commission, currency)
        values ($1, $2, $3, $4, $5, $6, $7)
        on conflict (provider, invoice_id) do nothing returning id
        """, r["affiliate_id"], user_id, provider, invoice_id, money(amount), com, (currency or "usd").lower())
    if r["first_paid_at"] is None:
        await db.execute("update referrals set first_paid_at = $2 where user_id = $1 and first_paid_at is null",
                         user_id, paid_at)
    return com if inserted else None


async def void_payment(provider: str, invoice_id: str, refunded: Any = None, total: Any = None) -> None:
    """Refund: void the commission (fully, or reduce it for a partial refund)."""
    if not invoice_id:
        return
    row = await db.fetchrow("select id, amount, commission, status from commissions "
                            "where provider = $1 and invoice_id = $2", provider, invoice_id)
    if not row or row["status"] == "void":
        return
    if refunded is not None and total and money(refunded) < money(total):
        keep = (money(total) - money(refunded)) / money(total)
        await db.execute("update commissions set commission = $2 where id = $1",
                         row["id"], money(Decimal(str(row["commission"])) * keep))
        return
    if row["status"] == "paid":
        log.warning("refund after commission %s was paid out — recover it manually", row["id"])
    await db.execute("update commissions set status = 'void' where id = $1 and status <> 'paid'", row["id"])


async def handle_stripe_event(event: dict) -> None:
    if not db.is_connected():
        return None
    etype = event.get("type", "")
    obj = (event.get("data") or {}).get("object") or {}
    if etype in ("invoice.paid", "invoice.payment_succeeded"):
        from . import repository
        sub_meta = ((obj.get("subscription_details") or {}).get("metadata") or {})
        user_id = sub_meta.get("user_id") or await repository.find_user_by_provider_id(
            obj.get("customer"), obj.get("subscription"))
        amount = obj.get("total_excluding_tax")
        if amount is None:
            amount = (obj.get("amount_paid") or 0) - (obj.get("tax") or 0)
        ts = obj.get("status_transitions", {}).get("paid_at") or obj.get("created")
        paid_at = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None
        await record_payment("stripe", user_id, obj.get("id"), Decimal(amount) / 100, obj.get("currency", "usd"), paid_at)
    elif etype == "charge.refunded" and obj.get("invoice"):
        await void_payment("stripe", obj["invoice"], Decimal(obj.get("amount_refunded") or 0) / 100,
                           Decimal(obj.get("amount") or 0) / 100)


async def handle_paypal_event(event: dict) -> None:
    if not db.is_connected():
        return None
    etype = event.get("event_type", "")
    res = event.get("resource") or {}
    if etype == "PAYMENT.SALE.COMPLETED":
        from . import repository
        sub_id = res.get("billing_agreement_id")
        user_id = res.get("custom") or await repository.find_user_by_provider_id(None, sub_id)
        amt = res.get("amount") or {}
        await record_payment("paypal", user_id, res.get("id"), amt.get("total"), amt.get("currency", "USD"))
    elif etype in ("PAYMENT.SALE.REFUNDED", "PAYMENT.SALE.REVERSED"):
        await void_payment("paypal", res.get("sale_id") or res.get("id"))


# ── reporting ────────────────────────────────────────────────────────────────
def link_for(code: str) -> str:
    return f"{config.APP_URL}/?ref={code}"


async def stats(affiliate_id: Any) -> dict:
    hold = datetime.now(timezone.utc) - timedelta(days=HOLD_DAYS)
    row = await db.fetchrow(
        """
        select
          (select count(*) from referrals where affiliate_id = $1) as signups,
          (select count(*) from referrals where affiliate_id = $1 and first_paid_at is not null) as customers,
          (select count(*) from referrals r join subscriptions s on s.user_id = r.user_id
            where r.affiliate_id = $1 and s.provider in ('stripe','paypal') and s.status = 'active') as active,
          coalesce((select sum(commission) from commissions where affiliate_id = $1 and status = 'pending'
                     and created_at > $2), 0) as on_hold,
          coalesce((select sum(commission) from commissions where affiliate_id = $1 and status = 'pending'
                     and created_at <= $2), 0) as payable,
          coalesce((select sum(commission) from commissions where affiliate_id = $1 and status = 'paid'), 0) as paid,
          coalesce((select sum(amount) from commissions where affiliate_id = $1 and status <> 'void'), 0) as revenue
        """, affiliate_id, hold)
    return {k: (float(v) if isinstance(v, Decimal) else v) for k, v in dict(row).items()}


async def monthly(affiliate_id: Any) -> list[dict]:
    rows = await db.fetch(
        """
        select to_char(date_trunc('month', created_at), 'YYYY-MM') as month,
               sum(commission) filter (where status <> 'void') as earned,
               count(*) filter (where status <> 'void') as payments
          from commissions where affiliate_id = $1 and created_at > now() - interval '12 months'
         group by 1 order by 1
        """, affiliate_id)
    return [{"month": r["month"], "earned": float(r["earned"] or 0), "payments": r["payments"]} for r in rows]


async def recent(affiliate_id: Any, limit: int = 25) -> list[dict]:
    hold = datetime.now(timezone.utc) - timedelta(days=HOLD_DAYS)
    rows = await db.fetch(
        "select id, amount, commission, currency, status, created_at, paid_at from commissions "
        "where affiliate_id = $1 order by created_at desc limit $2", affiliate_id, limit)
    out = []
    for r in rows:
        st = r["status"]
        if st == "pending":
            st = "on_hold" if r["created_at"] > hold else "payable"
        out.append({"id": str(r["id"]), "amount": float(r["amount"]), "commission": float(r["commission"]),
                    "currency": r["currency"], "status": st, "created_at": r["created_at"], "paid_at": r["paid_at"]})
    return out
