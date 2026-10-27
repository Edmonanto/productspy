"""One-off cleanup: remove "products" that aren't physical products.

    python -m app.winners.worker --clean              # every live market, then rescan
    python -m app.winners.worker --market US --clean

Earlier runs (with a looser prompt, or guesswork before an AI key was set)
could turn an app, a course, a store-wide sale or a clothing shop into a
"product". This asks the AI about every product that has ads in the given
markets, in batches: "is this ONE physical product an online store ships?".

For each "no":
  * its ads are set aside as not-a-product (never linked again),
  * the product is deleted — or, if someone has it in a watchlist or a quote,
    kept but marked non-physical so it can never be picked again,
  * it disappears from today's picks when the market is rescanned.
"""
from __future__ import annotations

import json
import logging

from app import db

from .filters import NON_PRODUCT_ADVERTISERS, non_product_reason
from .llm import llm_available, llm_json

log = logging.getLogger("winners.cleanup")

BATCH = 40

SYSTEM = ("You are a strict e-commerce analyst. You decide whether each item is ONE physical "
          "product that an online store ships. You answer with strict JSON only.")

PROMPT = """For each item below (a product name plus a sample of the ad text behind it), answer
true only if it is ONE specific physical product an online store ships to customers.

Answer false for: apps, games, software, websites, services, courses, coaching, events,
subscriptions, food/drinks/supplements/medicines, local businesses, finance/insurance,
a store, brand, collection, catalogue or sale, a general clothing/shoe/jewellery shop,
creator content, or anything too vague to be one item.

Return JSON: {{"keep": [<i of every item that IS one physical product>]}}

Items:
{items}
"""


async def _candidates(markets: list[str]) -> list[dict]:
    rows = await db.fetch(
        """
        select p.id, p.title,
               (select string_agg(left(coalesce(a.ad_text, ''), 160), ' | ')
                  from (select ad_text from ad_creatives a2
                         where a2.product_id = p.id order by a2.last_seen_at desc limit 2) a) as sample
          from products p
         where p.source = 'winners'
           and coalesce(p.attributes ->> 'physical', 'true') <> 'false'
           and exists (select 1 from ad_creatives a where a.product_id = p.id
                        and a.market = any($1::text[]))
        """,
        markets,
    )
    return [dict(r) for r in rows]


async def _remove(product_id) -> str:
    await db.execute(
        "update ad_creatives set product_id = null, not_product = true where product_id = $1",
        product_id)
    in_use = await db.fetchval(
        "select exists (select 1 from watchlists where product_id = $1) "
        "or exists (select 1 from quote_requests where product_id = $1)", product_id)
    if in_use:
        await db.execute(
            "update products set attributes = coalesce(attributes, '{}'::jsonb) || "
            "'{\"physical\": false}'::jsonb, updated_at = now() where id = $1", product_id)
        return "kept (in a watchlist/quote), never picked again"
    await db.execute("delete from daily_winners where product_id = $1", product_id)
    await db.execute("delete from winner_scores where product_id = $1", product_id)
    await db.execute("delete from products where id = $1", product_id)
    return "deleted"


async def clean(markets: list[str]) -> dict:
    """Run on an open db connection. Returns counts."""
    removed, unanswered, names = 0, 0, []
    # 1. Ads from app / media brands are never products, whatever they were linked to.
    pattern = "(" + "|".join(NON_PRODUCT_ADVERTISERS) + ")"
    freed = await db.fetchval(
        """
        with r as (update ad_creatives set product_id = null, not_product = true
                    where market = any($1::text[]) and advertiser_name ~* $2 returning 1)
        select count(*) from r
        """, markets, r"\m" + pattern + r"\M")
    log.info("clean: %s ads from app/media advertisers set aside", freed)
    # 2. Names that can't be a physical product (apps, dramas, courses...) — no AI needed.
    items = []
    for it in await _candidates(markets):
        why = non_product_reason(it["title"])
        if why:
            outcome = await _remove(it["id"])
            removed += 1
            names.append(it["title"])
            log.info("not a product: %s (%s) — %s", it["title"], why, outcome)
        else:
            items.append(it)
    if not llm_available():
        log.warning("--clean: no AI key, only the rule-based pass ran")
        return {"checked": 0, "removed": removed, "examples": names[:15], "note": "rules only (no AI key)"}
    # 3. The AI reviews the rest.
    for start in range(0, len(items), BATCH):
        chunk = items[start:start + BATCH]
        lines = "\n".join(json.dumps({"i": i, "product": it["title"], "ads": (it["sample"] or "")[:320]},
                                     ensure_ascii=False) for i, it in enumerate(chunk))
        res = await llm_json(SYSTEM, PROMPT.format(items=lines), max_tokens=1500)
        if not isinstance(res, dict) or not isinstance(res.get("keep"), list):
            unanswered += len(chunk)       # AI didn't answer: leave this batch alone
            continue
        keep = {int(i) for i in res["keep"] if isinstance(i, (int, float)) or str(i).isdigit()}
        for i, it in enumerate(chunk):
            if i not in keep:
                outcome = await _remove(it["id"])
                removed += 1
                names.append(it["title"])
                log.info("not a product: %s — %s", it["title"], outcome)
    return {"checked": len(items) - unanswered, "removed": removed, "unanswered": unanswered,
            "examples": names[:15]}
