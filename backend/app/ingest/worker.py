"""Ingestion worker — the engine behind the dashboard.

Per provider: fetch → upsert → snapshot → score → summarise. Run it on a
schedule (Render cron); each run also writes a `product_snapshots` row per
product, which is what makes trend scoring possible from the second week on.

    python -m app.ingest.worker
"""
import asyncio
import logging
import sys

from .. import config, db, repository, scoring, summarize
from ..providers.registry import enabled_providers

log = logging.getLogger("ingest")


async def ingest_provider(provider, limit: int) -> dict[str, int]:
    stats = {"fetched": 0, "upserted": 0, "scored": 0, "summarized": 0}
    run_id = await repository.start_run(provider.name)
    error: str | None = None
    # Demand is ranked within a source, so each source needs its own
    # distribution. Read once per run and reused for every product below.
    baselines: dict[str, list[int]] = {}

    try:
        await _apply_budget(provider)
        try:
            raw_products = await provider.fetch(limit)
        finally:
            # Persist paid calls even if fetch blew up halfway: those calls
            # were made and charged either way.
            await _record_usage(provider)

        if getattr(provider, "out_of_credits", None):
            spent = ", ".join(sorted(provider.out_of_credits))
            error = f"out of credits: {spent} token — top it up with the provider"
            log.error("%s: %s", provider.name, error)

        stats["fetched"] = len(raw_products)
        log.info("%s: fetched %d products", provider.name, len(raw_products))

        for raw in raw_products:
            try:
                product_id = await repository.upsert_product(raw)
                stats["upserted"] += 1

                if raw.ad_count is not None and raw.ad_platform:
                    await repository.record_ad_signal(
                        product_id, raw.ad_platform, raw.ad_count
                    )

                # Snapshot before scoring so today's values are on record even
                # if scoring or summarising fails below.
                await repository.write_snapshot(
                    product_id, raw.price_usd, raw.cost_usd,
                    raw.orders_count, raw.ad_count,
                )

                product = await repository.get_product(product_id)
                if product is None:
                    continue

                previous = await repository.orders_at(
                    product_id, config.TREND_WINDOW_DAYS
                )
                if raw.source not in baselines:
                    baselines[raw.source] = await repository.orders_baseline(
                        raw.source
                    )
                score = scoring.score_product(
                    product,
                    orders_count=raw.orders_count,
                    previous_orders=previous,
                    demand_baseline=baselines[raw.source],
                )

                # Only pay for a summary when there isn't one yet.
                if not score.ai_summary and config.ANTHROPIC_API_KEY:
                    summary = await summarize.summarize(product, score)
                    if summary:
                        score.ai_summary = summary
                        stats["summarized"] += 1

                await repository.save_score(product_id, score)
                stats["scored"] += 1

            except Exception as exc:
                # One bad product must not abort the run.
                log.warning("%s: skipped %s — %s", provider.name, raw.external_id, exc)

    except Exception as exc:
        error = str(exc)
        log.exception("%s: run failed", provider.name)

    await repository.finish_run(
        run_id, stats["fetched"], stats["upserted"],
        stats["scored"], stats["summarized"], error,
    )
    return stats


async def _apply_budget(provider) -> None:
    """Lower a metered provider's per-endpoint allowance by today's usage.

    Providers that aren't metered have no `daily_budgets` and are untouched.
    """
    budgets = getattr(provider, "daily_budgets", None)
    if not budgets:
        return
    used = await repository.api_calls_today(provider.name)
    provider.remaining = {ep: max(0, cap - used.get(ep, 0)) for ep, cap in budgets.items()}
    log.info("%s: calls left today %s (caps %s)", provider.name, provider.remaining, budgets)


async def _record_usage(provider) -> None:
    calls = getattr(provider, "call_log", None)
    if not calls:
        return
    try:
        await repository.record_api_calls(provider.name, calls)
    except Exception:
        # Accounting must not turn a good run into a failed one.
        log.exception("%s: could not record API usage", provider.name)


async def run(limit: int = config.INGEST_LIMIT) -> dict[str, int]:
    providers = enabled_providers()
    if not providers:
        log.error(
            "No providers configured. Set TIKTOK_TOKEN, AMAZON_TOKEN or "
            "AGG1688_SEARCH_TOKEN — see backend/README.md."
        )
        return {"fetched": 0, "upserted": 0, "scored": 0, "summarized": 0}

    await db.connect()
    totals = {"fetched": 0, "upserted": 0, "scored": 0, "summarized": 0}
    try:
        for provider in providers:
            stats = await ingest_provider(provider, limit)
            for key in totals:
                totals[key] += stats[key]
    finally:
        await db.disconnect()

    log.info("ingestion complete: %s", totals)
    return totals


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    totals = asyncio.run(run())
    # Non-zero exit makes a silent no-op run visible in Render's cron history.
    return 0 if totals["upserted"] else 1


if __name__ == "__main__":
    sys.exit(main())
