"""One market, one day:

    collect -> store ads -> name + dedupe products -> price & cost
            -> aggregate signals -> score -> pick 5-10 winners

Each step catches its own failures: a blocked collector or a failed price
lookup makes the run "partial", never empty-handed.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone

from . import store
from .collectors import Collector, active_collectors
from .enrich import fetch_selling_price, fetch_supplier_cost
from .extract import cluster_keys, guess_products_detailed
from .markets import get_market
from .scoring import aggregate, pick_winners, score

log = logging.getLogger("winners")


def _attrs(value) -> dict:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return {}
    return value or {}


async def collect_step(market_code: str, collectors: list[Collector], stats: dict, errors: list) -> None:
    market = get_market(market_code)
    for c in collectors:
        try:
            records = await c.collect(market)
            for rec in records:
                await store.upsert_ad(rec)
            stats[f"collected_{c.name}"] = len(records)
            log.info("[%s] %s: %d records", market_code, c.name, len(records))
        except Exception as exc:  # one blocked source must not kill the run
            log.exception("[%s] collector %s failed", market_code, c.name)
            errors.append({"step": c.name, "error": str(exc)[:500]})


async def extract_step(market_code: str, stats: dict) -> None:
    rows = await store.unlinked_ads(market_code)
    if not rows:
        stats["linked_ads"] = 0
        return
    ads = [store.row_to_ad(r) for r in rows]
    detailed = await guess_products_detailed(ads)
    guesses = cluster_keys([g for g, _ in detailed], await store.existing_keys())
    touched, not_products, unknown = set(), [], 0
    for row, ad, guess, (_, by_ai) in zip(rows, ads, guesses, detailed):
        if guess is None:
            if by_ai:            # the AI said it isn't a product: never look again
                not_products.append(str(row["id"]))
            else:                # heuristics couldn't tell: retry next run
                unknown += 1
            continue
        product_id = await store.upsert_product(guess, ad)
        await store.link_ad(str(row["id"]), product_id)
        touched.add(product_id)
    await store.mark_not_product(not_products)
    stats["linked_ads"] = len(rows) - len(not_products) - unknown
    stats["unidentified_ads"] = unknown
    stats["products_touched"] = len(touched)


async def enrich_step(market_code: str, stats: dict) -> None:
    market = get_market(market_code)
    done = 0
    for p in await store.products_needing_price(market_code):
        info = await fetch_selling_price(p["url"], market.currency)
        supplier = await fetch_supplier_cost(p["title"])
        cost, estimated = (supplier["cost_usd"], False) if supplier else (None, False)
        if cost is None:
            est = _attrs(p["attributes"]).get("est_cost_usd")
            if est:
                cost, estimated = float(est), True
        await store.save_prices(
            str(p["id"]), info.get("price_usd") if info else None, cost, estimated,
            info.get("image") if info else None,
        )
        if supplier:
            await store.add_supplier(str(p["id"]), supplier["platform"],
                                     supplier["supplier_url"], supplier["cost_usd"])
        done += 1
    stats["priced"] = done


async def score_step(market_code: str, day: date, stats: dict) -> None:
    now = datetime.now(timezone.utc)
    products = await store.market_products_with_ads(market_code)
    picked = await store.last_picks(market_code, day)
    scored, score_ids = [], {}
    for pid, (prod, ads) in products.items():
        attrs = _attrs(prod["attributes"])
        last = picked.get(pid)
        sig = aggregate(
            ads, now=now,
            sell_price_usd=float(prod["price_usd"]) if prod["price_usd"] is not None else None,
            cost_usd=float(prod["cost_usd"]) if prod["cost_usd"] is not None else None,
            cost_estimated=bool(prod["cost_estimated"]),
            wow=attrs.get("wow"), problem=attrs.get("problem"),
            ip_risk=attrs.get("ip_risk") or "none", restricted=bool(attrs.get("restricted")),
            fragile_heavy=bool(attrs.get("fragile_heavy")), seasonal=bool(attrs.get("seasonal")),
            physical=attrs.get("physical", True) is not False,
            last_picked_days_ago=(day - last).days if last else None,
        )
        res = score(sig)
        score_ids[pid] = await store.save_score(pid, market_code, day, res)
        scored.append((pid, res))
        # Product pages elsewhere in the app read ad_signals.
        if sig.meta_ads:
            await store.record_ad_signal(pid, "facebook", sig.advertisers or sig.meta_ads)
        if sig.tiktok_ads:
            await store.record_ad_signal(pid, "tiktok", sig.tiktok_ads)

    chosen = pick_winners(scored)
    await store.save_winners(market_code, day, chosen, score_ids)
    stats["scored"] = len(scored)
    stats["winners"] = sum(1 for *_, tier in chosen if tier == "winner")
    stats["rising"] = sum(1 for *_, tier in chosen if tier == "rising")
    stats["watch"] = sum(1 for *_, tier in chosen if tier == "watch")
    stats["top_score"] = max((r.total for _, r in scored if not r.excluded), default=0)


async def run_market(market_code: str, day: date | None = None,
                     collectors: list[Collector] | None = None) -> dict:
    market_code = get_market(market_code).code
    day = day or datetime.now(timezone.utc).date()
    stats: dict = {}
    errors: list = []
    run_id = await store.start_run(market_code)
    status = "ok"
    try:
        chosen_collectors = collectors if collectors is not None else active_collectors()
        await collect_step(market_code, chosen_collectors, stats, errors)
        collected = sum(v for k, v in stats.items() if k.startswith("collected_"))
        if chosen_collectors and collected == 0:
            # Every source came back empty without raising — almost always the
            # sites being unreachable (no VPN from mainland China, a blocked
            # IP) rather than a genuinely quiet day. Say so instead of "ok".
            errors.append({
                "step": "collect",
                "error": "No ads collected from any source. Facebook/TikTok were probably "
                         "unreachable or blocked (VPN off, or this server's IP blocked) — "
                         "set PROXY_URL or USE_APIFY=true.",
            })
        await extract_step(market_code, stats)
        try:
            await enrich_step(market_code, stats)
        except Exception as exc:
            log.exception("[%s] enrichment failed", market_code)
            errors.append({"step": "enrich", "error": str(exc)[:500]})
        await score_step(market_code, day, stats)
        if errors:
            status = "partial"
    except Exception as exc:
        log.exception("[%s] run failed", market_code)
        errors.append({"step": "pipeline", "error": str(exc)[:500]})
        status = "failed"
    await store.finish_run(run_id, status, stats, errors)
    return {"market": market_code, "status": status, "stats": stats, "errors": errors}
