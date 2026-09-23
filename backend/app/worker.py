"""Ingest worker: pulls config.TRENDING_KEYWORDS from 1688 into Postgres.

    python -m app.worker                # every seed keyword, page 1
    python -m app.worker --pages 2      # first two pages of each

Run on a schedule (render.yaml: productspy-ingest). Each keyword page costs one
metered search call unless it is still inside SEARCH_CACHE_TTL_HOURS. Daily
runs also build the sales snapshots that trend scoring needs.

Exits non-zero only if every keyword failed, so one bad keyword doesn't mark
the whole run as failed.
"""
import argparse
import asyncio
import logging
import sys

from . import config, db
from .services import catalog
from .sources.ali1688 import Ali1688Error

log = logging.getLogger("app.worker")


async def run(pages: int) -> int:
    await db.connect()
    ok = failed = 0
    try:
        for category, keywords in config.TRENDING_KEYWORDS.items():
            for keyword in keywords:
                for page in range(1, pages + 1):
                    try:
                        products, found = await catalog.search(keyword, page, category)
                    except Ali1688Error as exc:
                        failed += 1
                        log.error("%s / %r page %d: %s", category, keyword, page, exc)
                        break  # later pages of this keyword will fail the same way
                    ok += 1
                    log.info("%s / %r page %d: %d products (%d on 1688)",
                             category, keyword, page, len(products), found)
    finally:
        await db.disconnect()

    log.info("done: %d pages ingested, %d failed", ok, failed)
    return 1 if failed and not ok else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pages", type=int, default=1, help="result pages per keyword")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    sys.exit(asyncio.run(run(args.pages)))


if __name__ == "__main__":
    main()
