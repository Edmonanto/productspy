"""Matching pass: translate supplier titles, then score retail/supplier pairs.

Runs after ingestion. Two stages, both bounded:

  1. Translate 1688 titles that have no English rendering yet (batched,
     cached on the row, so each product is paid for once).
  2. For the highest-demand retail listings, score every translated supplier
     and keep the best few candidates.

Stage 2 is O(retail x suppliers), which is why both sides are capped by
config — comparing entire catalogues would be quadratic and would bury the
review queue in noise.

Nothing here changes a product's score. A match affects margin only once it
is `confirmed`, and v1's confidence cap means it never auto-confirms.
"""
import asyncio
import json
import logging
import sys

from .. import config, db, repository
from . import matcher, translate

log = logging.getLogger("matching")


async def translate_suppliers(limit: int) -> int:
    rows = await repository.untranslated_suppliers("1688", limit)
    if not rows:
        return 0

    items = [(str(r["id"]), r["title"]) for r in rows]
    log.info("matching: translating %d supplier titles", len(items))

    translations = await translate.translate_batch(items)
    for product_id, english in translations.items():
        await repository.save_translation(product_id, english)

    return len(translations)


async def match_products(retail_limit: int, supplier_limit: int) -> dict[str, int]:
    stats = {"retail": 0, "suppliers": 0, "candidates": 0, "rejected": 0}

    suppliers = [
        {"id": str(r["id"]), "title_en": r["title_en"], "cost_usd": float(r["cost_usd"])}
        for r in await repository.supplier_candidates(supplier_limit)
    ]
    stats["suppliers"] = len(suppliers)
    if not suppliers:
        log.info("matching: no translated suppliers yet — nothing to match against")
        return stats

    retail_rows = await repository.retail_products_for_matching(retail_limit)
    stats["retail"] = len(retail_rows)

    for row in retail_rows:
        retail = {
            "id": str(row["id"]),
            "title": row["title"],
            "price_usd": float(row["price_usd"]),
        }
        for supplier, result in matcher.best_matches(retail, suppliers):
            await repository.save_match(
                retail["id"], supplier["id"], result.confidence,
                result.method, json.dumps(result.evidence, ensure_ascii=False),
                result.status,
            )
            stats["candidates"] += 1
            log.info(
                "matching: %.2f %s <- %s (%s)",
                result.confidence, row["title"][:40],
                (supplier["title_en"] or "")[:40], result.status,
            )

    return stats


async def run() -> dict[str, int]:
    await db.connect()
    try:
        translated = await translate_suppliers(config.MATCH_TRANSLATE_LIMIT)
        stats = await match_products(
            config.MATCH_RETAIL_LIMIT, config.MATCH_SUPPLIER_LIMIT
        )
        stats["translated"] = translated
        counts = await repository.match_counts()
        log.info("matching complete: %s | totals in db: %s", stats, counts)
        return stats
    finally:
        await db.disconnect()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    stats = asyncio.run(run())
    # A run that matched nothing is usually a missing ANTHROPIC_API_KEY or an
    # empty catalogue, both worth surfacing in the cron history.
    return 0 if stats.get("candidates") else 1


if __name__ == "__main__":
    sys.exit(main())
