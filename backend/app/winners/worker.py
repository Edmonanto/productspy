"""Daily Winners worker — run once a day (Render cron).

    python -m app.winners.worker                 # every market in WINNERS_MARKETS
    python -m app.winners.worker --market US     # one market
    python -m app.winners.worker --collectors    # which sources are active
    (a run over every market ends by sending the daily winners email — see digest.py)
    python -m app.winners.worker --market US --recheck
                                                 # re-examine recent ads that were set
                                                 # aside as "not a product" (e.g. after
                                                 # adding an AI key)
    python -m app.winners.worker --market US --rebuild
                                                 # throw away products that were named
                                                 # by guesswork before an AI key was set,
                                                 # and let the AI name their ads again
    python -m app.winners.worker --clean         # AI reviews every product and removes
                                                 # anything that isn't a physical product
                                                 # (apps, courses, store-wide sales...),
                                                 # then rescans so today's picks are clean

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


REBUILD_SQL = """
with guessed as (
    select p.id from products p
     where p.source = 'winners'
       and not (coalesce(p.attributes, '{}'::jsonb) ? 'physical')   -- never seen by the AI
       and not exists (select 1 from watchlists w where w.product_id = p.id)
       and not exists (select 1 from quote_requests q where q.product_id = p.id)
), freed as (
    update ad_creatives set product_id = null, not_product = false
     where product_id in (select id from guessed)
    returning 1
), gone as (
    delete from products where id in (select id from guessed) returning 1
)
select (select count(*) from gone) as products, (select count(*) from freed) as ads
"""


async def run(markets: list[str], recheck: bool = False, rebuild: bool = False,
              clean: bool = False) -> list[dict]:
    await db.connect()
    results = []
    try:
        if rebuild:
            from .llm import llm_available
            if not llm_available():
                log.error("--rebuild needs ANTHROPIC_API_KEY or OPENAI_API_KEY; skipping it")
            else:
                row = await db.fetchrow(REBUILD_SQL)
                log.info("rebuild: removed %s guessed products, %s ads will be named again",
                         row["products"], row["ads"])
                recheck = True
        if clean:
            from .cleanup import clean as clean_products
            log.info("clean: %s", json.dumps(await clean_products(markets), ensure_ascii=False))
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
    ap.add_argument("--no-email", action="store_true", help="don't send the daily winners email")
    ap.add_argument("--rebuild", action="store_true",
                    help="remove products named by guesswork (before an AI key) and re-name their ads")
    ap.add_argument("--clean", action="store_true",
                    help="remove products that aren't physical products, then rescan")
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

    results = asyncio.run(run(markets, recheck=args.recheck, rebuild=args.rebuild, clean=args.clean))
    if not args.market and not args.no_email:
        # The scheduled run covers every market: email today's picks.
        from .digest import _run as send_daily_email
        log.info("daily email: %s", asyncio.run(send_daily_email(None)))
    produced = sum(r["stats"].get("winners", 0) + r["stats"].get("rising", 0) for r in results)
    return 0 if produced else 1


if __name__ == "__main__":
    sys.exit(main())
