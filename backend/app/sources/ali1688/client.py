"""HTTP access to the hosted 1688 search and detail endpoints.

Both endpoints are metered per call. Callers should go through
`app.services.catalog`, which caches in Postgres, rather than calling these
directly from a request handler.
"""
import logging
from typing import Any

import httpx

from ... import config
from . import parser
from .models import OfferDetail, SearchPage

log = logging.getLogger(__name__)


class Ali1688Error(Exception):
    """Upstream failure: network, bad token, out of credits, or bad payload."""


async def _get_json(url: str, params: dict[str, Any], token: str) -> dict[str, Any]:
    if not token:
        raise Ali1688Error("1688 API token is not configured")
    try:
        async with httpx.AsyncClient(timeout=config.ALI1688_TIMEOUT_SECONDS) as http:
            res = await http.get(url, params={**params, "token": token})
    except httpx.HTTPError as exc:
        raise Ali1688Error(f"1688 request failed: {exc.__class__.__name__}") from exc

    if res.status_code != 200:
        raise Ali1688Error(f"1688 returned HTTP {res.status_code}")
    if not res.content:
        raise Ali1688Error("1688 returned an empty response")
    try:
        body = res.json()
    except ValueError as exc:
        raise Ali1688Error("1688 returned invalid JSON") from exc

    # Error envelope for both endpoints: {"code": "error", "msg": "token次数不足"}
    if body.get("code") == "error":
        raise Ali1688Error(f"1688 error: {body.get('msg') or 'unknown'}")
    return body


async def search(keyword: str, page: int = 1) -> SearchPage:
    body = await _get_json(
        config.ALI1688_SEARCH_URL,
        {"keyword": keyword, "page": page},
        config.ALI1688_SEARCH_TOKEN,
    )
    return parser.parse_search(body, keyword, page)


async def fetch_detail(offer_id: str) -> OfferDetail:
    body = await _get_json(
        config.ALI1688_DETAIL_URL, {"itemId": offer_id}, config.ALI1688_DETAIL_TOKEN
    )
    ret = str(body.get("ret") or "")
    if ret and not ret.startswith("SUCCESS"):
        raise Ali1688Error(f"1688 detail error: {ret}")
    if "left_num" in body:
        log.info("1688 detail token calls remaining: %s", body["left_num"])

    detail = parser.parse_detail(body)
    if detail is None:
        raise Ali1688Error(f"1688 has no detail for offer {offer_id}")
    return detail
