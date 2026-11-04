"""Signup funnel events, split by language (en/fr).

    landing_view -> signup_click -> account_created -> winner_opened
                 -> checkout_started -> paid

The first two come from the landing page, anonymously (POST /events). The
rest are recorded server-side, once per user. Recording never fails a
request: analytics must not break signups or checkout.
"""
from __future__ import annotations

import logging
from typing import Any

from . import db

log = logging.getLogger(__name__)

ANONYMOUS_EVENTS = ("landing_view", "signup_click")
USER_EVENTS = ("account_created", "winner_opened", "checkout_started", "paid")
STEPS = ANONYMOUS_EVENTS + USER_EVENTS
LANGS = ("en", "fr")


def clean_lang(lang: str | None) -> str | None:
    lang = (lang or "").lower()[:2]
    return lang if lang in LANGS else None


async def record(event: str, *, user_id: str | None = None, lang: str | None = None,
                 source: str | None = None) -> None:
    if event not in STEPS or not db.is_connected():
        return
    try:
        await db.execute(
            "insert into funnel_events (event, user_id, lang, source) values ($1, $2, $3, $4) "
            "on conflict do nothing",
            event, user_id, clean_lang(lang), (source or "")[:40] or None,
        )
    except Exception:  # noqa: BLE001 — never let analytics fail the request
        log.exception("funnel event %s not recorded", event)


async def summary(days: int) -> dict[str, Any]:
    """Counts per step and language over the last `days` days.

    A user's later steps take the language of their account_created row, so a
    French signup who pays later still counts as French."""
    rows = await db.fetch(
        """
        with langs as (
            select user_id, lang from funnel_events
            where event = 'account_created' and user_id is not null
        )
        select e.event, coalesce(e.lang, l.lang, 'unknown') as lang, count(*) as n
        from funnel_events e left join langs l on l.user_id = e.user_id
        where e.created_at >= now() - make_interval(days => $1)
        group by 1, 2
        """,
        days,
    )
    counts: dict[str, dict[str, int]] = {s: {} for s in STEPS}
    for r in rows:
        if r["event"] in counts:
            counts[r["event"]][r["lang"]] = int(r["n"])
    sources = await db.fetch(
        """
        select coalesce(lang, 'unknown') as lang, coalesce(source, 'other') as source, count(*) as n
        from funnel_events
        where event = 'signup_click' and created_at >= now() - make_interval(days => $1)
        group by 1, 2 order by 3 desc
        """,
        days,
    )
    return {
        "days": days,
        "steps": [{"event": s, "by_lang": counts[s], "total": sum(counts[s].values())} for s in STEPS],
        "signup_click_sources": [dict(r) | {"n": int(r["n"])} for r in sources],
    }
