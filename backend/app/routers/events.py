"""/events — anonymous landing-page events in, funnel summary out (admin).

POST /events          {"event": "landing_view"|"signup_click", "lang": "fr", "source": "hero"}
GET  /events/funnel   ?days=30   ADMIN_EMAILS only

The POST body is sent with navigator.sendBeacon as text/plain (a "simple"
request, so no CORS preflight), hence the manual JSON parsing.
"""
from __future__ import annotations

import json
import time
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from .. import config, funnel
from ..auth import CurrentUser, current_user

router = APIRouter(prefix="/events", tags=["events"])

# Per-IP cap on anonymous events, in memory (per process): plenty for real
# visitors, and it keeps a script from filling the table. The IP is used only
# here and never stored.
RATE_PER_MINUTE = 30
_hits: dict[str, list[float]] = defaultdict(list)


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() or (request.client.host if request.client else "?")


def _allow(ip: str) -> bool:
    now = time.monotonic()
    recent = [t for t in _hits[ip] if now - t < 60]
    if len(recent) >= RATE_PER_MINUTE:
        _hits[ip] = recent
        return False
    recent.append(now)
    _hits[ip] = recent
    if len(_hits) > 10_000:  # forget idle visitors
        for k in [k for k, v in _hits.items() if not v or now - v[-1] > 60]:
            _hits.pop(k, None)
    return True


@router.post("", status_code=status.HTTP_204_NO_CONTENT)
async def post_event(request: Request) -> Response:
    raw = await request.body()
    try:
        body = json.loads(raw[:2000] or b"{}")
    except ValueError:
        body = None
    if not isinstance(body, dict) or body.get("event") not in funnel.ANONYMOUS_EVENTS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Unknown event")
    if _allow(_client_ip(request)):
        source = body.get("source")
        await funnel.record(body["event"], lang=body.get("lang"),
                            source=source if isinstance(source, str) else None)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/funnel")
async def get_funnel(days: int = Query(30, ge=1, le=365),
                     user: CurrentUser = Depends(current_user)) -> dict[str, Any]:
    if user.email.lower() not in config.ADMIN_EMAILS:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Admins only")
    return await funnel.summary(days)
