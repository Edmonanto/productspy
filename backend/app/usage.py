"""Metering and daily caps for paid APIs (OpenAI-compatible LLM, Apify).

Every call is counted in api_usage (provider, endpoint, day): calls, failures,
tokens and dataset items, so an unexpectedly expensive day is visible in
/admin/usage. A daily cap per provider (config.LLM_DAILY_CALL_CAP,
config.APIFY_DAILY_RUN_CAP; 0 = no cap) stops runaway spend: over the cap,
`allowed()` says no and the caller degrades gracefully.

Metering is best-effort — without a database (tests, scripts) it silently
does nothing and never blocks a call.
"""
from __future__ import annotations

import logging

from . import config, db

log = logging.getLogger("usage")

CAPS = {"llm": lambda: config.LLM_DAILY_CALL_CAP, "apify": lambda: config.APIFY_DAILY_RUN_CAP}


async def record(provider: str, endpoint: str, ok: bool = True, tokens_in: int = 0,
                 tokens_out: int = 0, items: int = 0, error: str | None = None) -> None:
    if not db.is_connected():
        return
    try:
        await db.execute(
            """
            insert into api_usage (provider, endpoint, calls, failures, tokens_in, tokens_out, items,
                                   last_error, updated_at)
            values ($1, $2, 1, $3, $4, $5, $6, $7, now())
            on conflict (provider, endpoint, usage_day) do update set
                calls = api_usage.calls + 1,
                failures = api_usage.failures + excluded.failures,
                tokens_in = api_usage.tokens_in + excluded.tokens_in,
                tokens_out = api_usage.tokens_out + excluded.tokens_out,
                items = api_usage.items + excluded.items,
                last_error = coalesce(excluded.last_error, api_usage.last_error),
                updated_at = now()
            """,
            provider, endpoint, 0 if ok else 1, int(tokens_in or 0), int(tokens_out or 0),
            int(items or 0), (error or None) and error[:300],
        )
    except Exception as exc:  # metering must never break the real work
        log.debug("usage record failed: %s", exc)


async def calls_today(provider: str) -> int:
    if not db.is_connected():
        return 0
    try:
        return int(await db.fetchval(
            "select coalesce(sum(calls), 0) from api_usage "
            "where provider = $1 and usage_day = (now() at time zone 'utc')::date", provider) or 0)
    except Exception:
        return 0


async def allowed(provider: str) -> bool:
    cap = CAPS.get(provider, lambda: 0)()
    if not cap:
        return True
    used = await calls_today(provider)
    if used >= cap:
        log.warning("%s daily cap reached (%s/%s) — call skipped", provider, used, cap)
        return False
    return True


async def summary(days: int = 14) -> list[dict]:
    rows = await db.fetch(
        """
        select usage_day, provider, endpoint, calls, failures, tokens_in, tokens_out, items, last_error
          from api_usage where usage_day >= (now() at time zone 'utc')::date - $1::int
         order by usage_day desc, provider, endpoint
        """, days)
    return [dict(r) | {"usage_day": r["usage_day"].isoformat()} for r in rows]
