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

from app import config

from . import store
from .collectors import Collector, active_collectors
from .enrich import fetch_selling_price, fetch_supplier_cost
from .angles import angles_step
from .trends import trends_step
from .extract import cluster_keys, guess_products_detailed
from .filters import is_catalog_template, non_product_advertiser, non_product_reason
from .markets import get_market
from .scoring import aggregate, pick_winners, score
from .llm import llm_available
from .verify import CANDIDATES, ad_key, verify_product

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
    # App / media brands (Canva, short-drama apps...) never sell a product: skip the AI.
    blocked = [str(r["id"]) for r in rows
               if non_product_advertiser(r.get("advertiser_name")) or is_catalog_template(r.get("ad_text"))]
    if blocked:
        await store.mark_not_product(blocked)
        rows = [r for r in rows if str(r["id"]) not in set(blocked)]
    stats["blocked_advertisers"] = len(blocked)
    if not rows:
        stats["linked_ads"] = 0
        return
    ads = [store.row_to_ad(r) for r in rows]
    detailed = await guess_products_detailed(ads)
    # The AI's product name must not be an app, service or digital item.
    detailed = [((None, True) if g is not None and non_product_reason(g.name, g.category) else (g, ai))
                for g, ai in detailed]
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


def _opt_bool(v):
    return None if v is None else bool(v)


def _signals(prod, ads, day: date, now: datetime, last, history: list | None = None,
             search: dict | None = None) -> "object":
    attrs = _attrs(prod["attributes"])
    ai_seen = "physical" in attrs          # attributes written by the AI pass
    return aggregate(
        ads, now=now,
        sell_price_usd=float(prod["price_usd"]) if prod["price_usd"] is not None else None,
        cost_usd=float(prod["cost_usd"]) if prod["cost_usd"] is not None else None,
        cost_estimated=bool(prod["cost_estimated"]),
        wow=attrs.get("wow"), problem=attrs.get("problem"), demo3s=_opt_bool(attrs.get("demo3s")),
        upsell=attrs.get("upsell"), brandable=attrs.get("brandable"),
        ip_risk=attrs.get("ip_risk") or ("none" if ai_seen else None),
        restricted=bool(attrs.get("restricted")),
        fragile_heavy=_opt_bool(attrs.get("fragile_heavy")) if ai_seen else None,
        seasonal=_opt_bool(attrs.get("seasonal")) if ai_seen else None,
        physical=attrs.get("physical", True) is not False
                 and not non_product_reason(prod["title"], prod.get("category")),
        last_picked_days_ago=(day - last).days if last else None,
        paid_ads_history=list(history or []),
        search_status=(search or {}).get("status"), search_growth=(search or {}).get("growth"),
        search_level=(search or {}).get("level"), search_term=(search or {}).get("term"),
        search_geo=(search or {}).get("geo"),
    )


async def verify_step(market_code: str, products: dict, results: dict, stats: dict,
                      day: date, now: datetime, picked: dict) -> set[str]:
    """Make sure the ads behind the leading products really advertise them.

    Returns the ids of products whose ads have all been checked (this run or
    an earlier one). Products that aren't physical products are excluded.
    """
    ranked = sorted((pid for pid, (r, _) in results.items() if not r.excluded),
                    key=lambda pid: results[pid][0].total, reverse=True)[:CANDIDATES]
    rejected = renamed = dropped = 0
    verified: set[str] = set()
    for pid in ranked:
        prod, ads = products[pid]
        attrs = _attrs(prod["attributes"])
        verdict = await verify_product(prod["title"], ads, set(attrs.get("verified_ads") or []))
        if verdict.not_product:
            await store.reject_ads(market_code, pid, ads)
            await store.mark_not_physical(pid)
            res = score(_signals(prod, [], day, now, picked.get(pid)))
            res.excluded = "not a physical product"
            results[pid] = (res, [])
            dropped += 1
            continue
        if verdict.verified:
            verified.add(pid)
        if not verdict.checked:
            continue
        if verdict.reject:
            await store.reject_ads(market_code, pid, verdict.reject)
            rejected += len(verdict.reject)
        await store.mark_verified(
            pid, [ad_key(a) for a in verdict.keep],
            verdict.best.thumbnail_url if verdict.best and verdict.best.thumbnail_url else None,
            verdict.name if verdict.name and verdict.name != prod["title"] else None,
        )
        renamed += bool(verdict.name and verdict.name != prod["title"])
        if not verdict.keep:
            res = score(_signals(prod, [], day, now, picked.get(pid)))
            res.excluded = "its ads don't show this product"
            results[pid] = (res, [])
            verified.discard(pid)
        elif verdict.reject:
            sig = _signals(prod, verdict.keep, day, now, picked.get(pid))
            results[pid] = (score(sig), verdict.keep)
    stats["ads_rejected"] = rejected
    stats["renamed"] = renamed
    stats["not_products_dropped"] = dropped
    stats["verified"] = len(verified)
    return verified


async def score_step(market_code: str, day: date, stats: dict, errors: list | None = None) -> None:
    errors = errors if errors is not None else []
    now = datetime.now(timezone.utc)
    products = await store.market_products_with_ads(market_code)
    picked = await store.last_picks(market_code, day)
    # Catalog-template ads never back a single product (see filters.is_catalog_template).
    template_ads = {pid: [a for a in ads if is_catalog_template(a.ad_text)] for pid, (_, ads) in products.items()}
    for pid, bad in template_ads.items():
        if bad:
            await store.reject_ads(market_code, pid, bad)
            prod, ads = products[pid]
            products[pid] = (prod, [a for a in ads if not is_catalog_template(a.ad_text)])
    products = {pid: v for pid, v in products.items() if v[1]}
    stats["template_ads_removed"] = sum(len(v) for v in template_ads.values())
    history = await store.paid_ads_history(market_code, list(products), day)
    results: dict = {}
    for pid, (prod, ads) in products.items():
        results[pid] = (score(_signals(prod, ads, day, now, picked.get(pid), history.get(pid))), ads)

    # Google search interest for the strongest candidates, then rescore them with it.
    try:
        ranked = sorted((pid for pid, (r, _) in results.items() if not r.excluded),
                        key=lambda pid: results[pid][0].total, reverse=True)
        searches = await trends_step(market_code, ranked, products, day, stats)
        for pid, data in searches.items():
            prod, ads = products[pid]
            results[pid] = (score(_signals(prod, ads, day, now, picked.get(pid), history.get(pid), data)), ads)
    except Exception as exc:
        log.warning("[%s] google trends skipped: %s", market_code, exc)
        errors.append({"step": "google_trends", "error": str(exc)[:500]})

    verified: set[str] | None = None
    try:
        verified = await verify_step(market_code, products, results, stats, day, now, picked)
    except Exception:   # a failed check must not cost the day's picks
        log.exception("[%s] verification failed", market_code)

    # With an AI key, only products whose ads were all checked can be picked —
    # so every pick is backed by ads that really sell it. (If the AI was down
    # and nothing could be checked, fall back to the unchecked ranking rather
    # than show an empty day.)
    if llm_available() and verified:
        for pid, (res, ads) in results.items():
            if pid not in verified and not res.excluded:
                res.excluded = "ads not checked yet"

    # Every pick needs a picture: use the product's own, else the best ad thumbnail.
    no_image = 0
    for pid, (res, ads) in results.items():
        prod = products[pid][0]
        if prod["image_url"]:
            continue
        thumb = next((a.thumbnail_url for a in sorted(ads, key=lambda a: a.platform != "meta")
                      if a.thumbnail_url and a.thumbnail_url.startswith("http")), None)
        if thumb:
            await store.set_image(pid, thumb)
        elif not res.excluded:
            res.excluded = "no product image"
            no_image += 1
    stats["no_image"] = no_image

    scored, score_ids = [], {}
    for pid, (res, ads) in results.items():
        score_ids[pid] = await store.save_score(pid, market_code, day, res)
        scored.append((pid, res))
        sig = res.signals or {}
        # Product pages elsewhere in the app read ad_signals.
        if sig.get("meta_ads"):
            await store.record_ad_signal(pid, "facebook", sig.get("advertisers") or sig["meta_ads"])
        if sig.get("tiktok_ads"):
            await store.record_ad_signal(pid, "tiktok", sig["tiktok_ads"])

    chosen = pick_winners(scored)
    await store.save_winners(market_code, day, chosen, score_ids)
    try:  # suggested marketing angles for the day's picks (never fails the run)
        await angles_step(market_code, [pid for pid, *_ in chosen], products, day, stats)
    except Exception:
        log.exception("[%s] angles failed", market_code)
    stats["scored"] = len(scored)
    stats["winners"] = sum(1 for *_, tier in chosen if tier == "winner")
    stats["rising"] = sum(1 for *_, tier in chosen if tier == "rising")
    stats["watch"] = sum(1 for *_, tier in chosen if tier == "watch")
    stats["top_score"] = max((r.total for _, r in scored if not r.excluded), default=0)


async def run_market(market_code: str, day: date | None = None,
                     collectors: list[Collector] | None = None, collect: str = "auto") -> dict:
    """collect: "auto" = scrape unless this market was scraped in the last
    APIFY_MIN_HOURS_BETWEEN hours (paid sources cost money per item); "always";
    "never" = re-process the ads already stored (no scraping, no cost)."""
    market_code = get_market(market_code).code
    day = day or datetime.now(timezone.utc).date()
    stats: dict = {}
    errors: list = []
    run_id = await store.start_run(market_code)
    status = "ok"
    try:
        chosen_collectors = collectors if collectors is not None else active_collectors()
        if collect == "never":
            chosen_collectors = []
            stats["collect_skipped"] = "re-processing stored ads (no scraping)"
        elif collect == "auto" and any(getattr(c, "paid", False) for c in chosen_collectors):
            since = await store.hours_since_collected(market_code)
            if since is not None and since < config.APIFY_MIN_HOURS_BETWEEN:
                chosen_collectors = [c for c in chosen_collectors if not getattr(c, "paid", False)]
                stats["collect_skipped"] = f"paid sources already scraped {since:.0f}h ago"
        await collect_step(market_code, chosen_collectors, stats, errors)
        collected = sum(v for k, v in stats.items() if k.startswith("collected_"))
        if chosen_collectors and collected == 0 and not errors:
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
        await score_step(market_code, day, stats, errors)
        if errors:
            status = "partial"
    except Exception as exc:
        log.exception("[%s] run failed", market_code)
        errors.append({"step": "pipeline", "error": str(exc)[:500]})
        status = "failed"
    await store.finish_run(run_id, status, stats, errors)
    return {"market": market_code, "status": status, "stats": stats, "errors": errors}
