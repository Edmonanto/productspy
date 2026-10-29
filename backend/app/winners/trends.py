"""Google Trends search interest via Apify (apify~google-trends-scraper).

For the strongest candidates of each market (TRENDS_CANDIDATES), fetch 12 months
of weekly search interest in that country and turn it into:

    status   rising | stable | falling | spike | low | no_data
    growth   last 4 weeks vs the 8 weeks before (ratio)
    level    average of the last 4 weeks (Google's 0-100 index, relative)
    series   the weekly points, for the chart on the product page

"spike" separates a short viral burst from sustained demand: the peak is in
the last few weeks and far above the product's normal level. Google Trends is
a relative index of searches, not sales or a search volume — it is labelled
that way everywhere it appears.

Cached per product and market for TRENDS_TTL_DAYS in products.attributes
(trends.<MARKET>). One Apify run per market per day at most; failures never
stop the scan.
"""
from __future__ import annotations

import json
import logging
from datetime import date
from statistics import mean, median
from typing import Any, Optional

from app import config, db

from .collectors.apify import _apify_on, run_actor_async
from .llm import _unwrap_list, llm_available, llm_json
from .markets import get_market

log = logging.getLogger("winners.trends")

TRENDS_TTL_DAYS = 7
TRENDS_CANDIDATES = config.APIFY_TRENDS_MAX
GEO = {"UK": "GB", "EU": ""}
LANG_NAME = {"fr": "French", "de": "German", "ar": "Arabic"}


def trends_on() -> bool:
    return _apify_on() and bool(config.APIFY_TRENDS_ACTOR)


def geo_for(market: str) -> str:
    return GEO.get(market, market)


# ── analysis ────────────────────────────────────────────────────────────────
def series_from_item(item: dict) -> list[dict]:
    """[{date, value}] from one Apify dataset item; drops the partial (current) week."""
    pts = []
    for p in item.get("interestOverTime_timelineData") or []:
        if p.get("isPartial"):
            continue
        val = p.get("value")
        v = val[0] if isinstance(val, list) and val else val
        try:
            ts = int(p.get("time"))
        except (TypeError, ValueError):
            continue
        if isinstance(v, (int, float)):
            pts.append({"date": date.fromtimestamp(ts).isoformat(), "value": int(v)})
    return pts


def analyze(series: list[dict]) -> dict:
    vals = [p["value"] for p in series]
    if len(vals) < 12 or max(vals, default=0) == 0:
        return {"status": "no_data", "growth": None, "level": None, "peak_weeks_ago": None}
    recent, prior = vals[-4:], vals[-12:-4]
    level = round(mean(recent), 1)
    base = mean(prior) or 0.0
    growth = round(level / base, 2) if base > 0 else (None if level == 0 else 9.99)
    peak = max(vals)
    peak_ago = len(vals) - 1 - max(i for i, v in enumerate(vals) if v == peak)
    typical = median(vals) or 0.0
    if level < 5 and peak < 30:
        status = "low"
    elif peak_ago <= 6 and typical < peak * 0.2 and peak >= 50:
        status = "spike"               # sudden burst far above the usual level
    elif growth is not None and growth >= 1.3 and level >= 10:
        status = "rising"
    elif growth is not None and growth <= 0.7:
        status = "falling"
    else:
        status = "stable"
    return {"status": status, "growth": growth, "level": level, "peak_weeks_ago": peak_ago}


def needs_refresh(cached: Optional[dict], today: date) -> bool:
    if not cached:
        return True
    try:
        return (today - date.fromisoformat(str(cached.get("at")))).days >= TRENDS_TTL_DAYS
    except ValueError:
        return True


def _attrs(prod: Any) -> dict:
    a = prod["attributes"]
    return a if isinstance(a, dict) else json.loads(a or "{}")


def cached_for(prod: Any, market: str) -> Optional[dict]:
    return (_attrs(prod).get("trends") or {}).get(market)


# ── search terms ────────────────────────────────────────────────────────────
TRANSLATE = """Translate each product name into the short search phrase a shopper in {country} would type
into Google in {language} (2-4 words, generic, no brand). Return {{"items": [{{"i": <index>, "term": str}}]}}.
Products:
{lines}"""


async def search_terms(names: list[str], market: str) -> list[str]:
    m = get_market(market)
    lang = LANG_NAME.get(m.language)
    terms = [n.lower() for n in names]
    if not lang or not llm_available():
        return terms
    raw = await llm_json("You translate product names into local search phrases. JSON only.",
                         TRANSLATE.format(country=m.name, language=lang,
                                          lines="\n".join(json.dumps({"i": i, "product": n}) for i, n in enumerate(names))),
                         max_tokens=1500, purpose="trends-terms")
    for row in _unwrap_list(raw) or []:
        if isinstance(row, dict) and str(row.get("i", "")).isdigit() and isinstance(row.get("term"), str):
            i = int(row["i"])
            if 0 <= i < len(terms) and row["term"].strip():
                terms[i] = row["term"].strip().lower()[:60]
    return terms


# ── fetch + store ───────────────────────────────────────────────────────────
async def fetch(terms: list[str], market: str) -> dict[str, list[dict]]:
    items = await run_actor_async(config.APIFY_TRENDS_ACTOR, {
        "searchTerms": terms, "isMultiple": False, "timeRange": "", "geo": geo_for(market),
        "skipDebugScreen": True, "maxItems": len(terms),
    })
    out: dict[str, list[dict]] = {}
    for it in items:
        if isinstance(it, dict):
            term = str(it.get("searchTerm") or it.get("inputUrlOrTerm") or "").strip().lower()
            if term:
                out[term] = series_from_item(it)
    return out


async def save(product_id: str, market: str, data: dict) -> None:
    await db.execute(
        """
        update products set attributes = jsonb_set(coalesce(attributes, '{}'::jsonb), '{trends}',
               coalesce(attributes -> 'trends', '{}'::jsonb) || jsonb_build_object($2::text, $3::jsonb)),
               updated_at = now()
         where id = $1
        """, product_id, market, json.dumps(data))


async def trends_step(market: str, ranked_ids: list[str], products: dict, today: date, stats: dict) -> dict[str, dict]:
    """Fetch/refresh search interest for the top candidates. Returns {pid: trends data} for all known."""
    known: dict[str, dict] = {}
    todo: list[tuple[str, Any]] = []
    for pid in ranked_ids[:TRENDS_CANDIDATES]:
        prod = products[pid][0]
        c = cached_for(prod, market)
        if c and not needs_refresh(c, today):
            known[pid] = c
        else:
            todo.append((pid, prod))
    stats["trends_cached"] = len(known)
    if not todo or not trends_on():
        stats["trends_fetched"] = 0
        return known
    terms = await search_terms([p["title"] for _, p in todo], market)
    got = await fetch(terms, market)
    fetched = 0
    for (pid, _), term in zip(todo, terms):
        series = got.get(term)
        if series is None:
            continue
        data = {"term": term, "geo": geo_for(market) or "worldwide", "at": today.isoformat(),
                "series": series[-52:], **analyze(series)}
        await save(pid, market, data)
        known[pid] = data
        fetched += 1
    stats["trends_fetched"] = fetched
    return known


# ── quick check from the command line ───────────────────────────────────────
#   python -m app.winners.trends "posture corrector" US
if __name__ == "__main__":
    import asyncio
    import sys

    term = sys.argv[1] if len(sys.argv) > 1 else "posture corrector"
    mk = (sys.argv[2] if len(sys.argv) > 2 else "US").upper()
    if not trends_on():
        sys.exit("Google Trends is off: needs USE_APIFY=true, APIFY_TOKEN and APIFY_TRENDS_ACTOR")
    from .collectors.apify import ApifyLimitError
    try:
        got = asyncio.run(fetch([term.lower()], mk))
    except ApifyLimitError as exc:
        sys.exit(str(exc))
    s = got.get(term.lower())
    if not s:
        sys.exit(f"No data returned for '{term}' in {mk}")
    a = analyze(s)
    print(f"{term} [{mk}] -> {a['status']} | last-4-weeks index {a['level']} | growth x{a['growth']} | {len(s)} weeks")
    print("last 12 weeks:", [p["value"] for p in s[-12:]])
