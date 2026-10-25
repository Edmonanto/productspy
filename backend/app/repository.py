"""Data access. Plain SQL against Postgres — no ORM.

Daily Winners queries live in app/winners/store.py; this module holds the
account side: watchlist, subscription, free trial and webhook ledger.
"""
from typing import Any

import asyncpg

from . import config, db, trial
from .schemas import Subscription, WatchedProduct


# ── Products (only what the watchlist needs) ────────────────────────────────
async def product_exists(product_id: str) -> bool:
    return bool(await db.fetchval("select 1 from products where id = $1", product_id))


async def product_title(product_id: str) -> str | None:
    """Title for a product (quote requests copy it at request time)."""
    return await db.fetchval("select title from products where id = $1", product_id)


# ── Watchlist ───────────────────────────────────────────────────────────────
async def watchlist(user_id: str) -> list[tuple[str, WatchedProduct, Any]]:
    """Saved products with their best recent Daily Winners score (any market)."""
    rows = await db.fetch(
        """
        select w.id as watch_id, w.added_at, p.id, p.title, p.image_url,
               p.price_usd, p.cost_usd,
               (select max(ws.total) from winner_scores ws
                 where ws.product_id = p.id
                   and ws.scored_on > (now() at time zone 'utc')::date - 7) as score,
               (select ws.market from winner_scores ws
                 where ws.product_id = p.id
                 order by ws.scored_on desc, ws.total desc limit 1) as market
          from watchlists w
          join products p on p.id = w.product_id
         where w.user_id = $1
         order by w.added_at desc
        """,
        user_id,
    )
    return [
        (
            str(r["watch_id"]),
            WatchedProduct(
                id=str(r["id"]),
                title=r["title"],
                image_url=r["image_url"],
                price_usd=float(r["price_usd"]) if r["price_usd"] is not None else None,
                cost_usd=float(r["cost_usd"]) if r["cost_usd"] is not None else None,
                score=r["score"],
                market=r["market"],
            ),
            r["added_at"],
        )
        for r in rows
    ]


async def watchlist_count(user_id: str) -> int:
    return int(
        await db.fetchval("select count(*) from watchlists where user_id = $1", user_id) or 0
    )


async def watchlist_add(user_id: str, product_id: str) -> None:
    await db.execute(
        "insert into watchlists (user_id, product_id) values ($1, $2) "
        "on conflict (user_id, product_id) do nothing",
        user_id,
        product_id,
    )


async def watchlist_remove(user_id: str, product_id: str) -> None:
    await db.execute(
        "delete from watchlists where user_id = $1 and product_id = $2",
        user_id,
        product_id,
    )


# ── Subscription ────────────────────────────────────────────────────
async def subscription(user_id: str) -> tuple[Subscription, str]:
    """Return the user's subscription and billing provider (defaults to free).

    `plan` is the *effective* plan: a free trial past its end reads as free
    here, before the daily job has rewritten the row. Every quota and feature
    check goes through this, so none of them can be fooled by a stale trial.
    """
    row = await db.fetchrow(
        "select plan, status, provider, current_period_end, trial_ends_at "
        "from subscriptions where user_id = $1",
        user_id,
    )
    if row is None:
        return Subscription(plan=config.DEFAULT_PLAN, status="active", current_period_end=None), "none"
    plan = trial.effective_plan(row["plan"], row["status"], row["provider"], row["trial_ends_at"])
    expired_trial = trial.is_app_trial(row["status"], row["provider"]) and plan == "free"
    return (
        Subscription(
            plan=plan,
            status="active" if expired_trial else row["status"],
            current_period_end=None if expired_trial else row["current_period_end"],
        ),
        row["provider"],
    )


async def subscription_row(user_id: str) -> asyncpg.Record | None:
    """Full subscription row, including the provider ids the API calls need."""
    return await db.fetchrow(
        "select plan, status, provider, provider_customer_id, "
        "provider_subscription_id, current_period_end, cancel_at_period_end, "
        "trial_started_at, trial_ends_at, trial_used, email "
        "from subscriptions where user_id = $1",
        user_id,
    )


# ── Free trial ──────────────────────────────────────────────────────────────
async def ensure_subscription(user_id: str, email: str) -> None:
    """First visit: start the no-card trial. Later visits: keep email current.

    `on conflict do nothing`-style for the trial itself — an existing row,
    paid or free, is never put back on a trial here.
    """
    await db.execute(
        """
        insert into subscriptions (user_id, plan, status, provider,
            current_period_end, trial_started_at, trial_ends_at, trial_used,
            email, updated_at)
        values ($1, $2, 'trialing', 'none', $3, now(), $3, true, $4, now())
        on conflict (user_id) do update set
            email = coalesce(nullif(excluded.email, ''), subscriptions.email)
        """,
        user_id,
        config.TRIAL_PLAN,
        trial.trial_end_from_now(),
        email,
    )


async def start_trial(user_id: str, email: str) -> bool:
    """Put an existing free account on the trial. False if not eligible.

    Eligible = never had a trial and not on a paid plan. The condition lives
    in the WHERE clause so two concurrent clicks can't both succeed.
    """
    row = await db.fetchrow(
        """
        update subscriptions set
            plan = $2, status = 'trialing', provider = 'none',
            current_period_end = $3, trial_started_at = now(), trial_ends_at = $3,
            trial_used = true, trial_reminder_sent_at = null,
            email = coalesce(nullif($4, ''), email), updated_at = now()
         where user_id = $1 and trial_used = false
           and (plan = 'free' or status = 'canceled')
        returning user_id
        """,
        user_id,
        config.TRIAL_PLAN,
        trial.trial_end_from_now(),
        email,
    )
    return row is not None


async def expire_trials() -> list[asyncpg.Record]:
    """Move every expired app trial to free; return who to notify."""
    return await db.fetch(
        """
        update subscriptions set
            plan = 'free', status = 'active', current_period_end = null, updated_at = now()
         where status = 'trialing' and provider = 'none'
           and trial_ends_at is not null and trial_ends_at <= now()
        returning user_id, email
        """
    )


async def trials_due_reminder() -> list[asyncpg.Record]:
    """Trials ending within 48h not reminded in the last 20h.

    Run daily, that is one email at ~2 days left and one on the last day.
    Marking and selecting in one statement means a re-run never double-sends.
    """
    return await db.fetch(
        """
        update subscriptions set trial_reminder_sent_at = now()
         where status = 'trialing' and provider = 'none'
           and trial_ends_at > now() and trial_ends_at <= now() + interval '48 hours'
           and (trial_reminder_sent_at is null
                or trial_reminder_sent_at < now() - interval '20 hours')
        returning user_id, email, trial_ends_at
        """
    )


async def upsert_subscription(
    user_id: str,
    plan: str,
    status: str,
    provider: str,
    customer_id: str | None = None,
    subscription_id: str | None = None,
    current_period_end: Any = None,
    cancel_at_period_end: bool = False,
) -> None:
    """Write subscription state. Only ever called from a verified webhook."""
    await db.execute(
        """
        insert into subscriptions (user_id, plan, status, provider,
            provider_customer_id, provider_subscription_id,
            current_period_end, cancel_at_period_end, updated_at)
        values ($1, $2, $3, $4, $5, $6, $7, $8, now())
        on conflict (user_id) do update set
            plan = excluded.plan,
            status = excluded.status,
            provider = excluded.provider,
            -- Keep known provider ids if a later event omits them.
            provider_customer_id = coalesce(
                excluded.provider_customer_id, subscriptions.provider_customer_id),
            provider_subscription_id = coalesce(
                excluded.provider_subscription_id, subscriptions.provider_subscription_id),
            current_period_end = coalesce(
                excluded.current_period_end, subscriptions.current_period_end),
            cancel_at_period_end = excluded.cancel_at_period_end,
            updated_at = now()
        """,
        user_id,
        plan,
        status,
        provider,
        customer_id,
        subscription_id,
        current_period_end,
        cancel_at_period_end,
    )


async def find_user_by_provider_id(
    customer_id: str | None, subscription_id: str | None
) -> str | None:
    """Recover our user id when an event carries no metadata."""
    row = await db.fetchrow(
        "select user_id from subscriptions "
        "where ($1::text is not null and provider_subscription_id = $1) "
        "   or ($2::text is not null and provider_customer_id = $2) limit 1",
        subscription_id,
        customer_id,
    )
    return str(row["user_id"]) if row else None


# ── Webhook idempotency ─────────────────────────────────────────────────────
async def claim_billing_event(provider: str, event_id: str, event_type: str) -> bool:
    """Record an event; return False if we have already seen it.

    Both providers retry on non-2xx and can deliver duplicates, so this is what
    stops a replayed event from applying twice.
    """
    row = await db.fetchrow(
        "insert into billing_events (provider, event_id, event_type) "
        "values ($1, $2, $3) on conflict (provider, event_id) do nothing "
        "returning id",
        provider,
        event_id,
        event_type,
    )
    return row is not None


async def complete_billing_event(
    provider: str, event_id: str, error: str | None = None
) -> None:
    await db.execute(
        "update billing_events set processed_at = now(), error = $3 "
        "where provider = $1 and event_id = $2",
        provider,
        event_id,
        error,
    )

# ── Quote requests ──────────────────────────────────────────────────────────
_QUOTE_COLUMNS = (
    "id, user_id, user_email, product_id, product_title, quantity, "
    "destination_country, target_price_usd, notes, status, quoted_unit_usd, "
    "quoted_shipping_usd, reply, created_at, replied_at"
)


async def create_quote(
    user_id: str,
    user_email: str,
    product_id: str,
    product_title: str,
    quantity: int,
    destination_country: str,
    target_price_usd: float | None,
    notes: str,
) -> asyncpg.Record:
    return await db.fetchrow(
        """
        insert into quote_requests (user_id, user_email, product_id, product_title,
            quantity, destination_country, target_price_usd, notes)
        values ($1, $2, $3, $4, $5, $6, $7, $8)
        returning id, user_id, user_email, product_id, product_title, quantity,
            destination_country, target_price_usd, notes, status, quoted_unit_usd,
            quoted_shipping_usd, reply, created_at, replied_at
        """,
        user_id, user_email, product_id, product_title, quantity,
        destination_country, target_price_usd, notes,
    )


async def quotes_created_today(user_id: str) -> int:
    return int(
        await db.fetchval(
            "select count(*) from quote_requests where user_id = $1 "
            "and created_at >= (now() at time zone 'utc')::date",
            user_id,
        )
        or 0
    )


async def list_quotes(user_id: str | None, limit: int = 100) -> list[asyncpg.Record]:
    """A user's own quotes, or every quote when user_id is None (admins)."""
    if user_id is None:
        return await db.fetch(
            f"select {_QUOTE_COLUMNS} from quote_requests "
            "order by (status = 'open') desc, created_at desc limit $1",
            limit,
        )
    return await db.fetch(
        f"select {_QUOTE_COLUMNS} from quote_requests "
        "where user_id = $1 order by created_at desc limit $2",
        user_id,
        limit,
    )


async def reply_quote(
    quote_id: str,
    status: str,
    quoted_unit_usd: float | None,
    quoted_shipping_usd: float | None,
    reply: str,
) -> asyncpg.Record | None:
    return await db.fetchrow(
        """
        update quote_requests set
            status = $2, quoted_unit_usd = $3, quoted_shipping_usd = $4,
            reply = $5, replied_at = now()
        where id = $1
        returning id, user_id, user_email, product_id, product_title, quantity,
            destination_country, target_price_usd, notes, status, quoted_unit_usd,
            quoted_shipping_usd, reply, created_at, replied_at
        """,
        quote_id, status, quoted_unit_usd, quoted_shipping_usd, reply,
    )
