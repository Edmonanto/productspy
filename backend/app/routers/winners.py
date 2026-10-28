"""/winners — the Daily Winners picks, evidence, and market preferences.

  GET  /winners/markets                 markets, plan limits, what the user follows
  POST /winners/preferences             {"markets": ["US", "AE"]}
  GET  /winners?market=US&date=         today's (or the latest) 5-10 picks
  GET  /winners/dates?market=US         archive days this plan can see
  GET  /winners/status                  last worker run per market
  GET  /winners/products/{id}?market=   everything behind one pick
  GET  /winners/export.csv?market=US    CSV (Pro / Agency)

Plan limits come from config.WINNERS_PLANS and are enforced here, not in the
UI: a locked pick is returned as {rank, total, locked: true} with nothing else.
"""
import csv
import io
import json
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from .. import config, repository
from ..auth import CurrentUser, current_user
from ..winners import digest, store
from ..winners.markets import DEFAULT_MARKET, MARKETS, market_public

router = APIRouter(prefix="/winners", tags=["winners"])

from ..winners.scoring import CRITERIA, CRITERIA_LABEL, band
from ..winners import economics

PILLARS = tuple(CRITERIA)


# ── helpers ─────────────────────────────────────────────────────────────────
async def _entitlements(user: CurrentUser) -> tuple[str, dict[str, Any]]:
    subscription, _ = await repository.subscription(user.id)  # effective plan (trial-aware)
    plan = subscription.plan if subscription.plan in config.WINNERS_PLANS else config.DEFAULT_PLAN
    return plan, {"plan": plan, **config.WINNERS_PLANS[plan]}


def _locked(error: str, message: str) -> HTTPException:
    return HTTPException(
        status.HTTP_403_FORBIDDEN,
        detail={"error": error, "message": message, "upgrade_url": "/dashboard/billing"},
    )


def _live() -> list[str]:
    """Markets that are scanned and offered (WINNERS_MARKETS), in that order."""
    live = [c for c in config.winners_markets() if c in MARKETS]
    return live or [DEFAULT_MARKET]


def _check_live(code: str) -> None:
    if code not in MARKETS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"Unknown market '{code}'")
    if code not in _live():
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            detail=f"{MARKETS[code].name} isn't available yet")


async def _followed(user_id: str) -> list[str]:
    live = _live()
    return [c for c in await store.followed_markets(user_id) if c in live]


async def _resolve_market(user: CurrentUser, market: str | None) -> tuple[str, dict[str, Any]]:
    """Validate the market and enforce how many markets the plan includes."""
    _, ent = await _entitlements(user)
    followed = await _followed(user.id)
    code = (market or (followed[0] if followed else _live()[0])).upper()
    _check_live(code)
    allowed = followed[: ent["markets"]]
    if code in allowed:
        return code, ent
    if len(allowed) < ent["markets"]:
        await store.save_followed_markets(user.id, allowed + [code])
        return code, ent
    raise _locked(
        "market_locked",
        f"Your {ent['plan']} plan includes {ent['markets']} market(s): {', '.join(allowed)}. "
        "Switch market in Settings or upgrade.",
    )


def _json(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


def _f(value: Any) -> float | None:
    return float(value) if value is not None else None


def serialize_pick(r: Any) -> dict[str, Any]:
    sig = _json(r["signals"]) or {}
    attrs = _json(r["attributes"]) or {}
    price, cost = _f(r["price_usd"]), _f(r["cost_usd"])
    econ = economics.for_product(price, cost)
    return {
        "rank": r["rank"], "tier": r["tier"], "total": r["total"], "locked": False,
        "band": sig.get("band") or band(r["total"]),
        "trend": sig.get("trend") or "unknown",
        "trend_why": sig.get("trend_why"),
        "strengths": sig.get("strengths") or [],
        "weaknesses": sig.get("weaknesses") or [],
        "missing": sig.get("missing_pillars") or [],
        "scored_on": r["pick_date"].isoformat() if r.get("pick_date") else None,
        "economics": {"complete": econ.complete,
                      "contribution_before_ads_usd": econ.contribution_before_ads_usd,
                      "contribution_margin_pct": econ.contribution_margin_pct,
                      "break_even_roas": econ.break_even_roas},
        "breakdown": _json(r["breakdown"]) or {},
        "angles": attrs.get("angles") or [],
        "reasons": _json(r["reasons"]) or [],
        "penalties": _json(r["penalties"]) or [],
        "confidence": r["confidence"],
        "product": {
            "id": str(r["product_id"]), "title": r["title"], "image_url": r["image_url"],
            "category": r["category"], "price_usd": price, "cost_usd": cost,
            "cost_estimated": bool(r["cost_estimated"]),
            "margin_pct": round((price - cost) / price * 100) if price and cost else None,
        },
        "stats": {
            "days_running": sig.get("max_days_running"),
            "creatives": sig.get("creatives"),
            "new_creatives_7d": sig.get("new_creatives_7d"),
            "stores": sig.get("advertisers"),
            "videos": sig.get("videos"),
            "views": sig.get("total_views"),
            "engagement_rate": sig.get("engagement_rate"),
            "intent_ratio": sig.get("intent_ratio"),
            "ctr": sig.get("best_ctr"),
            "sources": [name for name, key in (("facebook_ads", "meta_ads"), ("tiktok_ads", "tiktok_ads"),
                                               ("tiktok_organic", "videos")) if sig.get(key)],
        },
        "links": {
            "store_url": r["store_url"] or (r["product_url"] or None),
            "ad_url": r["ad_url"],
            "supplier_url": r["supplier_url"],
        },
    }


def _today() -> date:
    return datetime.now(timezone.utc).date()


# ── routes ──────────────────────────────────────────────────────────────────
@router.get("/markets")
async def list_markets(user: CurrentUser = Depends(current_user)) -> dict[str, Any]:
    _, ent = await _entitlements(user)
    followed = (await _followed(user.id))[: ent["markets"]]
    return {
        "markets": [market_public(MARKETS[c]) for c in _live()],
        "following": followed or [_live()[0]],
        "entitlements": ent,
        "plans": {k: {"plan": k, **v} for k, v in config.WINNERS_PLANS.items()},
    }


class PreferencesIn(BaseModel):
    markets: list[str]


class DigestIn(BaseModel):
    on: bool


@router.get("/digest")
async def get_digest(user: CurrentUser = Depends(current_user)) -> dict[str, Any]:
    """Is the daily winners email on for this user?"""
    return {"on": await digest.get_digest(user.id)}


@router.post("/digest")
async def set_digest(body: DigestIn, user: CurrentUser = Depends(current_user)) -> dict[str, Any]:
    await digest.set_digest(user.id, body.on)
    return {"on": body.on}


@router.get("/digest/unsubscribe", response_class=HTMLResponse)
async def unsubscribe(u: str = Query(...), t: str = Query(...)) -> HTMLResponse:
    """One-click unsubscribe from the email footer (signed link, no login)."""
    try:
        uuid.UUID(u)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid link")
    if not digest.valid_token(u, t):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid link")
    await digest.set_digest(u, False)
    return HTMLResponse(
        '<div style="font-family:Arial,sans-serif;max-width:420px;margin:80px auto;text-align:center">'
        "<h2>You're unsubscribed</h2><p>You won't get the daily winners email any more. "
        f'You can switch it back on in <a href="{config.APP_URL}/dashboard/settings">Settings</a>.</p></div>'
    )


@router.post("/preferences")
async def save_preferences(body: PreferencesIn, user: CurrentUser = Depends(current_user)) -> dict[str, Any]:
    _, ent = await _entitlements(user)
    codes: list[str] = []
    for c in body.markets:
        c = c.upper()
        _check_live(c)
        if c not in codes:
            codes.append(c)
    if not codes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Pick at least one market")
    if len(codes) > ent["markets"]:
        raise _locked("too_many_markets", f"Your {ent['plan']} plan allows {ent['markets']} market(s).")
    await store.save_followed_markets(user.id, codes)
    return {"markets": codes, "max_markets": ent["markets"]}


@router.get("")
async def get_winners(
    market: str | None = Query(None),
    day: date | None = Query(None, alias="date"),
    user: CurrentUser = Depends(current_user),
) -> dict[str, Any]:
    code, ent = await _resolve_market(user, market)
    today = _today()
    if day is not None and day < today - timedelta(days=int(ent["history_days"])):
        raise _locked("history_locked",
                      f"Your {ent['plan']} plan includes {ent['history_days']} days of history.")
    pick_date = await store.latest_pick_date(code, day or today)
    if not pick_date:
        return {"market": code, "date": None, "winners": [], "locked_count": 0, "plan": ent["plan"],
                "message": "No picks yet for this market — the first daily scan hasn't finished."}
    rows = await store.picks(code, pick_date)
    visible = int(ent["winners_per_day"])
    winners = [serialize_pick(r) for r in rows[:visible]]
    winners += [{"rank": r["rank"], "tier": r["tier"], "total": r["total"], "locked": True}
                for r in rows[visible:]]
    return {"market": code, "date": pick_date.isoformat(), "winners": winners,
            "locked_count": max(0, len(rows) - visible), "plan": ent["plan"]}


@router.get("/dates")
async def winner_dates(market: str | None = None, user: CurrentUser = Depends(current_user)) -> dict[str, Any]:
    code, ent = await _resolve_market(user, market)
    rows = await store.pick_dates(code, _today() - timedelta(days=int(ent["history_days"])))
    return {"market": code, "history_days": ent["history_days"],
            "dates": [{"date": r["pick_date"].isoformat(), "winners": r["winners"], "total": r["total"]}
                      for r in rows]}


@router.get("/status")
async def run_status(user: CurrentUser = Depends(current_user)) -> dict[str, Any]:
    rows = await store.latest_runs()
    def problem(errors: Any) -> str | None:
        errs = _json(errors) or []
        return errs[0].get("error") if errs and isinstance(errs[0], dict) else None

    return {"runs": [{
        "market": r["market"], "started_at": r["started_at"], "finished_at": r["finished_at"],
        "status": r["status"], "stats": _json(r["stats"]) or {},
        # First error of the run, so the dashboard can say why a market is empty.
        "problem": problem(r["errors"]),
    } for r in rows]}


def _score_out(latest: Any) -> dict[str, Any]:
    sig = _json(latest["signals"]) or {}
    return {
        "scored_on": latest["scored_on"].isoformat(), "total": latest["total"],
        "breakdown": _json(latest["breakdown"]), "reasons": _json(latest["reasons"]),
        "penalties": _json(latest["penalties"]), "confidence": latest["confidence"],
        "excluded": latest["excluded"],
        "band": sig.get("band") or band(latest["total"]),
        "criteria": sig.get("criteria") or {},
        "trend": sig.get("trend") or "unknown", "trend_why": sig.get("trend_why"),
        "strengths": sig.get("strengths") or [], "weaknesses": sig.get("weaknesses") or [],
        "missing": sig.get("missing_pillars") or [],
        "known_points": sig.get("known_points"),
        "signals": {k: sig.get(k) for k in (
            "advertisers", "creatives", "new_creatives_7d", "new_creatives_14d", "new_creatives_30d",
            "max_days_running", "median_days_running", "meta_ads", "tiktok_ads", "videos", "creators",
            "total_views", "engagement_rate", "intent_ratio", "views_per_hour", "first_seen_days",
            "paid_ads_history", "search_status", "search_growth", "search_level", "search_term", "search_geo")},
    }


@router.get("/products/{product_id}")
async def product_evidence(product_id: str, market: str | None = None,
                           user: CurrentUser = Depends(current_user)) -> dict[str, Any]:
    try:
        uuid.UUID(product_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Product not found")
    code, ent = await _resolve_market(user, market)
    p = await store.product(product_id)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Product not found")

    history = await store.score_history(product_id, code)
    latest = history[0] if history else None
    now = datetime.now(timezone.utc)
    ads: dict[str, list[dict[str, Any]]] = {"meta": [], "tiktok_ads": [], "tiktok_organic": []}
    counts: dict[str, int] = {}
    for a in await store.product_ads(product_id, code):
        counts[a["platform"]] = counts.get(a["platform"], 0) + 1
        bucket = ads.setdefault(a["platform"], [])
        if ent["ad_evidence"] and len(bucket) < 12:
            item = dict(a)
            item["ctr"] = _f(a["ctr"])
            item["days_running"] = (now - a["started_at"]).days if a["started_at"] else None
            bucket.append(item)

    attrs = _json(p["attributes"]) or {}
    price, cost = _f(p["price_usd"]), _f(p["cost_usd"])
    return {
        "market": code,
        "product": {
            "id": str(p["id"]), "title": p["title"], "image_url": p["image_url"],
            "category": p["category"], "price_usd": price, "cost_usd": cost,
            "cost_estimated": bool(p["cost_estimated"]),
            "margin_pct": round((price - cost) / price * 100) if price and cost else None,
            "product_url": p["product_url"] or None, "first_seen_at": p["first_seen_at"],
            "attributes": {k: attrs.get(k) for k in
                           ("wow", "problem", "demo3s", "upsell", "brandable", "ip_risk", "fragile_heavy", "seasonal")},
            "angles": attrs.get("angles") or [],
        },
        "search_trend": (attrs.get("trends") or {}).get(code),
        "score": None if latest is None else _score_out(latest),
        "criteria_labels": CRITERIA_LABEL,
        "assumptions": economics.DEFAULTS,
        "history": [{"date": h["scored_on"].isoformat(), "total": h["total"],
                     "paid_ads": ((_json(h["signals"]) or {}).get("meta_ads") or 0)
                                 + ((_json(h["signals"]) or {}).get("tiktok_ads") or 0),
                     "videos": (_json(h["signals"]) or {}).get("videos") or 0}
                    for h in reversed(history)],
        "suppliers": [{"platform": s["platform"], "supplier_name": s["supplier_name"],
                       "supplier_url": s["supplier_url"], "unit_cost_usd": _f(s["unit_cost_usd"])}
                      for s in await store.product_suppliers(product_id)],
        "ads": ads if ent["ad_evidence"] else {},
        "ad_counts": counts,
        "ad_evidence_locked": not ent["ad_evidence"],
    }


@router.get("/export.csv")
async def export_csv(market: str | None = None, day: date | None = Query(None, alias="date"),
                     user: CurrentUser = Depends(current_user)) -> StreamingResponse:
    _, ent = await _entitlements(user)
    if not ent["export_csv"]:
        raise _locked("export_locked", "CSV export is on the Pro and Agency plans.")
    code, _ = await _resolve_market(user, market)
    pick_date = await store.latest_pick_date(code, day or _today())
    rows = await store.picks(code, pick_date) if pick_date else []
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["date", "market", "rank", "tier", "score", "product", "category", "price_usd",
                "cost_usd", "margin_pct", "days_running", "creatives", "stores", "views",
                "store_url", "ad_url", "supplier_url", "reasons"])
    for r in rows:
        s = serialize_pick(r)
        pr, st, ln = s["product"], s["stats"], s["links"]
        w.writerow([pick_date, code, s["rank"], s["tier"], s["total"], pr["title"], pr["category"],
                    pr["price_usd"], pr["cost_usd"], pr["margin_pct"], st["days_running"],
                    st["creatives"], st["stores"], st["views"], ln["store_url"], ln["ad_url"],
                    ln["supplier_url"], " | ".join(s["reasons"])])
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="winners-{code}-{pick_date or "none"}.csv"'},
    )
