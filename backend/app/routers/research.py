"""/research — AI research reports, the validation workflow, comparison, usage.

  GET  /research/{product_id}/report?market=US      latest report (any status) + today's quota
  POST /research/{product_id}/report?market=US      generate (or return the cached one)
  GET  /research/{product_id}/validation            the user's 8-stage checklist + real results
  PUT  /research/{product_id}/validation/{stage}    {status, notes, links}
  PUT  /research/{product_id}/results               supplier quote, test spend, orders...
  GET  /research/compare?ids=a,b,c&market=US        up to the plan's compare_max products
  GET  /research/usage                              admins: paid API usage, last 14 days

Every route checks the user server-side; validation data belongs to its user
only. AI reports are cached (config.RESEARCH_CACHE_DAYS) and limited per plan
per day (reports_per_day); a cached or in-progress report costs nothing.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, HttpUrl

from .. import config, db, usage
from ..auth import CurrentUser, current_user
from ..winners import economics, research, store
from ..winners.scoring import CRITERIA, CRITERIA_LABEL
from .winners import _entitlements, _json, _locked, _resolve_market

router = APIRouter(prefix="/research", tags=["research"])

STAGES = [
    ("discovery", "Initial discovery"),
    ("demand", "Demand verification"),
    ("competitors", "Competitor research"),
    ("supplier", "Supplier & sample verification"),
    ("economics", "Unit economics validation"),
    ("creative", "Creative testing"),
    ("market_test", "Initial market testing"),
    ("decision", "Launch decision"),
]
STAGE_KEYS = {k for k, _ in STAGES}


def _uuid(value: str) -> str:
    try:
        return str(uuid.UUID(value))
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Product not found")


async def _product(product_id: str) -> dict:
    p = await store.product(product_id)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Product not found")
    d = dict(p)
    d["attributes"] = _json(d.get("attributes")) or {}
    for k in ("price_usd", "cost_usd"):
        d[k] = float(d[k]) if d.get(k) is not None else None
    return d


def _report_out(row: Optional[dict]) -> Optional[dict]:
    if not row:
        return None
    return {"id": str(row["id"]), "status": row["status"], "report": _json(row.get("report")),
            "warnings": _json(row.get("warnings")) or [], "model": row.get("model"),
            "error": row.get("error"), "created_at": row["created_at"], "finished_at": row.get("finished_at")}


# ── AI research report ───────────────────────────────────────────────────────
@router.get("/{product_id}/report")
async def get_report(product_id: str, market: str | None = None,
                     user: CurrentUser = Depends(current_user)) -> dict[str, Any]:
    product_id = _uuid(product_id)
    code, ent = await _resolve_market(user, market)
    await _product(product_id)
    return {"market": code, "report": _report_out(await research.latest_report(product_id, code)),
            "quota": {"used": await research.reports_today(user.id), "limit": ent.get("reports_per_day", 0)}}


@router.post("/{product_id}/report", status_code=status.HTTP_202_ACCEPTED)
async def create_report(product_id: str, background: BackgroundTasks, market: str | None = None,
                        refresh: bool = False, user: CurrentUser = Depends(current_user)) -> dict[str, Any]:
    product_id = _uuid(product_id)
    code, ent = await _resolve_market(user, market)
    product = await _product(product_id)
    history = await store.score_history(product_id, code)
    latest_score = dict(history[0]) if history else None

    cached = await research.cached_report(product_id, code)
    if cached and cached["status"] == "pending":
        return {"market": code, "report": _report_out(cached), "cached": True}
    if cached and cached["status"] == "ready":
        # Refreshing only makes sense when the evidence changed since the report.
        newer = latest_score and latest_score["scored_on"] > cached["created_at"].date()
        if not (refresh and newer):
            return {"market": code, "report": _report_out(cached), "cached": True}

    limit = int(ent.get("reports_per_day", 0))
    if await research.reports_today(user.id) >= limit:
        raise _locked("report_quota", f"Your {ent['plan']} plan includes {limit} AI research report(s) a day.")

    if latest_score:
        for k in ("signals", "breakdown"):
            latest_score[k] = _json(latest_score.get(k))
    ads = [dict(a) for a in await store.product_ads(product_id, code)]
    suppliers = [dict(s) | {"unit_cost_usd": float(s["unit_cost_usd"]) if s["unit_cost_usd"] is not None else None}
                 for s in await store.product_suppliers(product_id)]
    rid = await research.start(product_id, code, user.id)
    background.add_task(research.generate, rid, product, latest_score, ads, suppliers, code)
    return {"market": code, "report": {"id": rid, "status": "pending", "report": None, "warnings": [],
                                       "created_at": datetime.now(timezone.utc)}, "cached": False}


# ── validation workflow ──────────────────────────────────────────────────────
class StepIn(BaseModel):
    status: Literal["not_started", "in_progress", "completed", "blocked"]
    notes: str = Field(default="", max_length=4000)
    links: list[HttpUrl] = Field(default_factory=list, max_length=10)


class ResultsIn(BaseModel):
    supplier_quote_usd: Optional[float] = Field(default=None, ge=0, le=100000)
    shipping_quote_usd: Optional[float] = Field(default=None, ge=0, le=100000)
    selling_price_usd: Optional[float] = Field(default=None, ge=0, le=100000)
    ad_spend_usd: Optional[float] = Field(default=None, ge=0, le=10_000_000)
    orders: Optional[int] = Field(default=None, ge=0, le=10_000_000)
    revenue_usd: Optional[float] = Field(default=None, ge=0, le=100_000_000)
    refunds: Optional[int] = Field(default=None, ge=0, le=10_000_000)
    decision: Optional[Literal["launch", "iterate", "drop"]] = None


def _f(v: Any) -> Optional[float]:
    return float(v) if v is not None else None


def compare_actuals(product: dict, r: dict) -> dict:
    """The user's real numbers against the research assumptions — all deterministic."""
    price = r.get("selling_price_usd") or product.get("price_usd")
    cost = r.get("supplier_quote_usd") if r.get("supplier_quote_usd") is not None else product.get("cost_usd")
    inputs = economics.Inputs(price_usd=price, product_cost_usd=cost)
    if r.get("shipping_quote_usd") is not None:
        inputs.shipping_usd = r["shipping_quote_usd"]
    planned = economics.compute(inputs)
    out: dict[str, Any] = {"planned": vars(planned), "actual": {}, "notes": []}
    spend, orders, revenue = r.get("ad_spend_usd"), r.get("orders"), r.get("revenue_usd")
    if spend and orders:
        cpa = spend / orders
        out["actual"]["cpa_usd"] = round(cpa, 2)
        if planned.complete:
            out["actual"]["contribution_after_ads_usd"] = round(planned.contribution_before_ads_usd - cpa, 2)
            out["notes"].append(
                f"Actual cost per order ${cpa:.2f} vs break-even ${planned.break_even_cpa_usd:.2f}: "
                + ("profitable per order" if cpa < (planned.break_even_cpa_usd or 0) else "losing money per order"))
    if spend and revenue:
        roas = revenue / spend
        out["actual"]["roas"] = round(roas, 2)
        if planned.break_even_roas:
            out["notes"].append(f"Actual ROAS {roas:.2f} vs break-even {planned.break_even_roas:.2f}")
    if orders and r.get("refunds") is not None:
        out["actual"]["refund_rate_pct"] = round(r["refunds"] / orders * 100, 1)
    if r.get("supplier_quote_usd") is not None and product.get("cost_usd"):
        diff = r["supplier_quote_usd"] - product["cost_usd"]
        out["notes"].append(f"Supplier quote is ${abs(diff):.2f} {'above' if diff > 0 else 'below'} "
                            f"the {'estimated' if product.get('cost_estimated') else 'listed'} cost")
    return out


@router.get("/{product_id}/validation")
async def get_validation(product_id: str, user: CurrentUser = Depends(current_user)) -> dict[str, Any]:
    product_id = _uuid(product_id)
    product = await _product(product_id)
    rows = {r["stage"]: r for r in await db.fetch(
        "select stage, status, notes, links, updated_at from validation_steps "
        "where user_id = $1 and product_id = $2", user.id, product_id)}
    results = await db.fetchrow(
        "select supplier_quote_usd, shipping_quote_usd, selling_price_usd, ad_spend_usd, orders, "
        "revenue_usd, refunds, decision, updated_at from validation_results "
        "where user_id = $1 and product_id = $2", user.id, product_id)
    res = {k: (_f(v) if k.endswith("_usd") else v) for k, v in dict(results).items()} if results else {}
    steps = [{"stage": k, "label": label, "status": rows[k]["status"] if k in rows else "not_started",
              "notes": rows[k]["notes"] if k in rows else "", "links": _json(rows[k]["links"]) if k in rows else [],
              "updated_at": rows[k]["updated_at"] if k in rows else None} for k, label in STAGES]
    done = sum(1 for s in steps if s["status"] == "completed")
    return {"product_id": product_id, "steps": steps, "progress": {"completed": done, "total": len(steps)},
            "results": res, "comparison": compare_actuals(product, res) if res else None}


@router.put("/{product_id}/validation/{stage}")
async def put_step(product_id: str, stage: str, body: StepIn,
                   user: CurrentUser = Depends(current_user)) -> dict[str, Any]:
    product_id = _uuid(product_id)
    if stage not in STAGE_KEYS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Unknown stage")
    await _product(product_id)
    await db.execute(
        """
        insert into validation_steps (user_id, product_id, stage, status, notes, links, updated_at)
        values ($1, $2, $3, $4, $5, $6::jsonb, now())
        on conflict (user_id, product_id, stage) do update set status = excluded.status,
            notes = excluded.notes, links = excluded.links, updated_at = now()
        """, user.id, product_id, stage, body.status, body.notes, json.dumps([str(u) for u in body.links]))
    return {"stage": stage, "status": body.status}


@router.put("/{product_id}/results")
async def put_results(product_id: str, body: ResultsIn,
                      user: CurrentUser = Depends(current_user)) -> dict[str, Any]:
    product_id = _uuid(product_id)
    product = await _product(product_id)
    d = body.model_dump()
    await db.execute(
        """
        insert into validation_results (user_id, product_id, supplier_quote_usd, shipping_quote_usd,
            selling_price_usd, ad_spend_usd, orders, revenue_usd, refunds, decision, updated_at)
        values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, now())
        on conflict (user_id, product_id) do update set
            supplier_quote_usd = excluded.supplier_quote_usd, shipping_quote_usd = excluded.shipping_quote_usd,
            selling_price_usd = excluded.selling_price_usd, ad_spend_usd = excluded.ad_spend_usd,
            orders = excluded.orders, revenue_usd = excluded.revenue_usd, refunds = excluded.refunds,
            decision = excluded.decision, updated_at = now()
        """, user.id, product_id, d["supplier_quote_usd"], d["shipping_quote_usd"], d["selling_price_usd"],
        d["ad_spend_usd"], d["orders"], d["revenue_usd"], d["refunds"], d["decision"])
    return {"results": d, "comparison": compare_actuals(product, d)}


# ── comparison ───────────────────────────────────────────────────────────────
@router.get("/compare")
async def compare(ids: str = Query(..., max_length=400), market: str | None = None,
                  user: CurrentUser = Depends(current_user)) -> dict[str, Any]:
    code, ent = await _resolve_market(user, market)
    wanted = [i for i in dict.fromkeys(x.strip() for x in ids.split(",")) if i]
    cap = int(ent.get("compare_max", 2))
    if len(wanted) > cap:
        raise _locked("compare_limit", f"Your {ent['plan']} plan compares up to {cap} products.")
    items = []
    for pid in wanted:
        pid = _uuid(pid)
        p = await store.product(pid)
        if p is None:
            continue
        hist = await store.score_history(pid, code)
        s = hist[0] if hist else None
        sig = _json(s["signals"]) if s else {}
        price, cost = _f(p["price_usd"]), _f(p["cost_usd"])
        items.append({
            "id": pid, "title": p["title"], "image_url": p["image_url"], "category": p["category"],
            "price_usd": price, "cost_usd": cost, "cost_estimated": bool(p["cost_estimated"]),
            "score": s["total"] if s else None, "confidence": s["confidence"] if s else None,
            "scored_on": s["scored_on"].isoformat() if s else None,
            "breakdown": _json(s["breakdown"]) if s else {},
            "trend": (sig or {}).get("trend"), "band": (sig or {}).get("band"),
            "stores": (sig or {}).get("advertisers"), "videos": (sig or {}).get("videos"),
            "economics": vars(economics.for_product(price, cost)),
            "weaknesses": (sig or {}).get("weaknesses", []), "excluded": s["excluded"] if s else None,
        })
    return {"market": code, "items": items, "max": cap,
            "criteria": [{"key": k, "label": CRITERIA_LABEL[k], "max": round(w, 1)} for k, w in CRITERIA.items()]}


# ── admin: usage ─────────────────────────────────────────────────────────────
@router.get("/usage")
async def usage_report(user: CurrentUser = Depends(current_user)) -> dict[str, Any]:
    if user.email.lower() not in config.ADMIN_EMAILS:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Admins only")
    reports = await db.fetch(
        "select date_trunc('day', created_at)::date as day, status, count(*) as n, "
        "coalesce(sum(tokens_in), 0) as tin, coalesce(sum(tokens_out), 0) as tout "
        "from product_reports where created_at > now() - interval '14 days' group by 1, 2 order by 1 desc")
    return {"api": await usage.summary(14),
            "caps": {"llm_calls_per_day": config.LLM_DAILY_CALL_CAP, "apify_runs_per_day": config.APIFY_DAILY_RUN_CAP},
            "reports": [{"day": r["day"].isoformat(), "status": r["status"], "count": r["n"],
                         "tokens_in": r["tin"], "tokens_out": r["tout"]} for r in reports]}
