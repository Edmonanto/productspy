"""/partners — coach referral program.

Public
  POST /partners/click            {code}            count a link visit
  GET  /partners/offer?code=                         partner name + discount, for the landing banner
Signed-in
  POST /partners/attribute        {code}            link this new account to a partner
  GET  /partners/me                                  partner dashboard (or who referred me)
  PUT  /partners/me/payout        {method, details} how the partner wants to be paid
Admin (ADMIN_EMAILS)
  GET  /partners/admin                               all partners + stats
  POST /partners/admin            {name, email, code, ...}
  PATCH /partners/admin/{id}      {status, commission_pct, discount_pct, commission_months}
  GET  /partners/admin/payouts                       payable commissions grouped by partner
  POST /partners/admin/payouts    {affiliate_id, payout_ref}   mark everything payable as paid
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from .. import config, db, partners
from ..auth import CurrentUser, current_user

router = APIRouter(prefix="/partners", tags=["partners"])


def _is_admin(user: CurrentUser) -> bool:
    return user.email.lower() in config.ADMIN_EMAILS


def _admin(user: CurrentUser = Depends(current_user)) -> CurrentUser:
    if not _is_admin(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Admins only")
    return user


class CodeIn(BaseModel):
    code: str = Field(min_length=3, max_length=24)


# ── public ───────────────────────────────────────────────────────────────────
@router.post("/click")
async def click(body: CodeIn) -> dict[str, bool]:
    return {"ok": await partners.record_click(body.code)}


@router.get("/offer")
async def offer(code: str) -> dict[str, Any]:
    a = await partners.affiliate_by_code(code)
    if not a or a["status"] != "active":
        return {"valid": False}
    return {"valid": True, "code": a["code"], "partner": a["name"], "discount_pct": float(a["discount_pct"])}


# ── signed-in ────────────────────────────────────────────────────────────────
@router.post("/attribute")
async def attribute(body: CodeIn, user: CurrentUser = Depends(current_user)) -> dict[str, Any]:
    ok, reason = await partners.attribute(user.id, user.email, body.code)
    return {"ok": ok, "reason": reason}


@router.get("/me")
async def me(user: CurrentUser = Depends(current_user)) -> dict[str, Any]:
    out: dict[str, Any] = {"is_admin": _is_admin(user), "partner": None, "referred_by": None}
    r = await partners.referral_of(user.id)
    if r:
        out["referred_by"] = {"partner": r["name"], "discount_pct": float(r["discount_pct"]),
                              "discount_used": r["first_paid_at"] is not None}
    a = await partners.affiliate_for_user(user.id, user.email)
    if a:
        out["partner"] = {
            "name": a["name"], "code": a["code"], "link": partners.link_for(a["code"]),
            "status": a["status"], "commission_pct": float(a["commission_pct"]),
            "commission_months": a["commission_months"], "discount_pct": float(a["discount_pct"]),
            "payout_method": a["payout_method"], "payout_details": a["payout_details"],
            "clicks": a["clicks"], "hold_days": partners.HOLD_DAYS,
            "stats": await partners.stats(a["id"]),
            "monthly": await partners.monthly(a["id"]),
            "recent": await partners.recent(a["id"]),
        }
    return out


class PayoutIn(BaseModel):
    method: Literal["paypal", "wise", "bank", "other"]
    details: str = Field(min_length=3, max_length=500)


@router.put("/me/payout")
async def set_payout(body: PayoutIn, user: CurrentUser = Depends(current_user)) -> dict[str, str]:
    a = await partners.affiliate_for_user(user.id, user.email)
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="You are not a partner")
    await db.execute("update affiliates set payout_method = $2, payout_details = $3 where id = $1",
                     a["id"], body.method, body.details.strip())
    return {"message": "Payout details saved"}


# ── admin ────────────────────────────────────────────────────────────────────
class PartnerIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=200)
    code: str = Field(min_length=3, max_length=24)
    commission_pct: float = Field(default=30, ge=0, le=90)
    commission_months: int = Field(default=12, ge=1, le=120)
    discount_pct: float = Field(default=25, ge=0, le=90)


class PartnerPatch(BaseModel):
    status: Optional[Literal["active", "paused"]] = None
    commission_pct: Optional[float] = Field(default=None, ge=0, le=90)
    commission_months: Optional[int] = Field(default=None, ge=1, le=120)
    discount_pct: Optional[float] = Field(default=None, ge=0, le=90)


@router.get("/admin")
async def admin_list(_: CurrentUser = Depends(_admin)) -> dict[str, Any]:
    rows = await db.fetch("select * from affiliates order by created_at desc")
    items = []
    for a in rows:
        items.append({"id": str(a["id"]), "name": a["name"], "email": a["email"], "code": a["code"],
                      "link": partners.link_for(a["code"]), "status": a["status"],
                      "commission_pct": float(a["commission_pct"]), "commission_months": a["commission_months"],
                      "discount_pct": float(a["discount_pct"]), "clicks": a["clicks"],
                      "payout_method": a["payout_method"], "payout_details": a["payout_details"],
                      "linked": a["user_id"] is not None, "stats": await partners.stats(a["id"])})
    return {"partners": items, "hold_days": partners.HOLD_DAYS}


@router.post("/admin", status_code=status.HTTP_201_CREATED)
async def admin_create(body: PartnerIn, _: CurrentUser = Depends(_admin)) -> dict[str, Any]:
    code = partners.clean_code(body.code)
    if not code:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            detail="Code: 3-24 letters, numbers, - or _ (e.g. COACHMIKE)")
    if await db.fetchval("select 1 from affiliates where code = $1", code):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="That code is taken")
    rid = await db.fetchval(
        "insert into affiliates (name, email, code, commission_pct, commission_months, discount_pct) "
        "values ($1, $2, $3, $4, $5, $6) returning id",
        body.name.strip(), str(body.email).lower(), code, body.commission_pct, body.commission_months, body.discount_pct)
    return {"id": str(rid), "code": code, "link": partners.link_for(code)}


@router.patch("/admin/{affiliate_id}")
async def admin_update(affiliate_id: str, body: PartnerPatch, _: CurrentUser = Depends(_admin)) -> dict[str, str]:
    try:
        uuid.UUID(affiliate_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Partner not found")
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        return {"message": "Nothing to change"}
    sets = ", ".join(f"{k} = ${i + 2}" for i, k in enumerate(fields))
    done = await db.execute(f"update affiliates set {sets} where id = $1", affiliate_id, *fields.values())
    if done.endswith(" 0"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Partner not found")
    return {"message": "Updated"}


@router.get("/admin/payouts")
async def admin_payouts(_: CurrentUser = Depends(_admin)) -> dict[str, Any]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=partners.HOLD_DAYS)
    rows = await db.fetch(
        """
        select a.id, a.name, a.email, a.payout_method, a.payout_details, c.currency,
               sum(c.commission) as total, count(*) as n, min(c.created_at) as oldest
          from commissions c join affiliates a on a.id = c.affiliate_id
         where c.status = 'pending' and c.created_at <= $1
         group by a.id, a.name, a.email, a.payout_method, a.payout_details, c.currency
         order by total desc
        """, cutoff)
    return {"payouts": [{"affiliate_id": str(r["id"]), "name": r["name"], "email": r["email"],
                         "payout_method": r["payout_method"], "payout_details": r["payout_details"],
                         "currency": r["currency"], "total": float(r["total"]), "payments": r["n"],
                         "oldest": r["oldest"]} for r in rows]}


class PayIn(BaseModel):
    affiliate_id: str
    payout_ref: str = Field(min_length=2, max_length=120)


@router.post("/admin/payouts")
async def admin_mark_paid(body: PayIn, _: CurrentUser = Depends(_admin)) -> dict[str, Any]:
    try:
        uuid.UUID(body.affiliate_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Partner not found")
    cutoff = datetime.now(timezone.utc) - timedelta(days=partners.HOLD_DAYS)
    n = await db.fetchval(
        """
        with u as (update commissions set status = 'paid', paid_at = now(), payout_ref = $3
                    where affiliate_id = $1 and status = 'pending' and created_at <= $2 returning 1)
        select count(*) from u
        """, body.affiliate_id, cutoff, body.payout_ref.strip())
    return {"marked_paid": n}
