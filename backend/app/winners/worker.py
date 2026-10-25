"""Daily Winners worker — run once a day (Render cron).

    python -m app.winners.worker                 # every market in WINNERS_MARKETS
    python -m app.winners.worker --market US     # one market
    python -m app.winners.worker --collectors    # which sources are active
    python -m app.winners.worker --market US --recheck
                                                 # re-examine recent ads that were set
                                                 # aside as "not a product" (e.g. after
                                                 # adding ANTHROPIC_API_KEY)

Exits non-zero when no market produced picks, so a silent no-op shows up red
in Render's cron history (same rule as app.ingest.worker).
"""
import argparse
import asyncio
import json
import logging
import sys

from app import config, db

from .collectors import active_collectors
from .markets import MARKETS
from .pipeline import run_market

log = logging.getLogger("winners")


async def run(markets: list[str], recheck: bool = False) -> list[dict]:
    await db.connect()
    results = []
    try:
        if recheck:
            n = await db.fetchval(
                "with r as (update ad_creatives set not_product = false "
                " where market = any($1::text[]) and not_product and product_id is null "
                "   and last_seen_at > now() - interval '3 days' returning 1) "
                "select count(*) from r", markets)
            log.info("recheck: %s set-aside ads will be looked at again", n)
        for m in markets:
            res = await run_market(m)
            log.info("%s -> %s %s", m, res["status"], json.dumps(res["stats"]))
            results.append(res)
    finally:
        await db.disconnect()
    return results


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    ap = argparse.ArgumentParser()
    ap.add_argument("--market", default="", help="market code; default: WINNERS_MARKETS")
    ap.add_argument("--collectors", action="store_true", help="list active sources and exit")
    ap.add_argument("--recheck", action="store_true",
                    help="re-examine recent ads previously set aside as not a product")
    args = ap.parse_args()

    if args.collectors:
        for c in active_collectors():
            print(f"{c.name:28} {'paid' if c.paid else 'free'}")
        return 0

    markets = [args.market.upper()] if args.market else config.winners_markets()
    unknown = [m for m in markets if m not in MARKETS]
    if unknown:
        log.error("unknown market(s) %s; choose from %s", unknown, ", ".join(MARKETS))
        return 2

    results = asyncio.run(run(markets, recheck=args.recheck))
    produced = sum(r["stats"].get("winners", 0) + r["stats"].get("rising", 0) for r in results)
    return 0 if produced else 1


if __name__ == "__main__":
    sys.exit(main())
