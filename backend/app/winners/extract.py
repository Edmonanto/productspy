"""
Turn raw ads/videos into *products*.

1. AI pass (Claude / OpenAI): for each ad, name the single physical product
   it sells in generic words ("posture corrector", not "BackFix Pro"), give a
   canonical kebab-case key, and flag risks (brand/IP copy, restricted,
   fragile/heavy, seasonal) + "wow" and "solves a problem" ratings and a rough
   supplier unit cost.
2. Heuristic fallback when no AI key: Shopify /products/<slug> URLs and ad
   titles.
3. Clustering: keys that are near-duplicates ("posture-corrector" vs
   "back-posture-corrector") collapse onto the existing product.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Optional
from urllib.parse import urlparse

from .collectors.base import AdRecord
from .llm import _unwrap_list, llm_available, llm_json

STOPWORDS = {
    "the", "a", "an", "and", "for", "with", "of", "to", "in", "on", "new", "best", "pro", "premium",
    "original", "official", "sale", "free", "shipping", "buy", "shop", "now", "off", "get", "your",
    "my", "2024", "2025", "2026", "edition", "version", "upgraded", "set", "kit", "pack", "pcs",
    "le", "la", "les", "de", "du", "des", "pour", "avec", "et",
}
GENERIC_SLUGS = {"collections", "all", "products", "shop", "home", "pages", "index"}


@dataclass
class ProductGuess:
    key: str
    name: str
    category: Optional[str] = None
    attributes: dict = field(default_factory=dict)
    est_cost_usd: Optional[float] = None


def slugify(text: str, max_words: int = 5) -> str:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    words = [w for w in words if w not in STOPWORDS and not w.isdigit()]
    return "-".join(words[:max_words])


def key_tokens(key: str) -> set[str]:
    toks = set()
    for t in key.split("-"):
        if not t:
            continue
        toks.add(t[:-1] if len(t) > 3 and t.endswith("s") else t)  # naive singular
    return toks


def similar(a: str, b: str) -> float:
    ta, tb = key_tokens(a), key_tokens(b)
    if not ta or not tb:
        return 0.0
    jacc = len(ta & tb) / len(ta | tb)
    contain = len(ta & tb) / min(len(ta), len(tb))
    seq = SequenceMatcher(None, "-".join(sorted(ta)), "-".join(sorted(tb))).ratio()
    # "posture-corrector" fully contained in "back-posture-corrector" -> same product
    if contain == 1.0 and min(len(ta), len(tb)) >= 2:
        return max(0.9, jacc)
    return max(jacc, seq if seq > 0.9 else 0)


def match_existing(key: str, existing: list[str], threshold: float = 0.8) -> Optional[str]:
    if key in existing:
        return key
    best, best_s = None, 0.0
    for e in existing:
        s = similar(key, e)
        if s > best_s:
            best, best_s = e, s
    return best if best_s >= threshold else None


# ------------------------------------------------------------- heuristics

def shopify_slug(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    path = urlparse(url).path
    m = re.search(r"/products?/([a-z0-9\-]+)", path, re.I)
    if m and m.group(1).lower() not in GENERIC_SLUGS:
        return m.group(1).lower()
    return None


def heuristic_guess(ad: AdRecord) -> Optional[ProductGuess]:
    slug = shopify_slug(ad.landing_url)
    if slug:
        name = " ".join(w for w in slug.split("-") if w not in STOPWORDS and not w.isdigit())[:80]
        key = slugify(name)
        if key:
            return ProductGuess(key=key, name=name.title())
    if ad.platform != "tiktok_organic" and ad.ad_text:
        title = ad.ad_text.split("|")[0]
        title = re.sub(r"[#@]\S+", "", title).strip()
        key = slugify(title, 4)
        if len(key.split("-")) >= 2:
            return ProductGuess(key=key, name=title[:80])
    return None


# ------------------------------------------------------------- AI

SYSTEM = (
    "You are a senior e-commerce product researcher. You read ad copy and identify the ONE physical "
    "product being sold. You answer with strict JSON only."
)

PROMPT = """For each ad below, identify the single physical product it sells.

Return a JSON object {{"items": [...]}} with one object per ad:
{{"i": <index>, "product": "<generic product name in English, 2-5 words, no brand>" or null,
  "key": "<kebab-case canonical key, e.g. posture-corrector>",
  "category": "<one of: home, kitchen, beauty, health, fitness, pets, baby, kids-toys, fashion-accessories, tech-gadgets, car, outdoor, tools, other>",
  "wow": <0-10 how visually impressive / scroll-stopping>,
  "problem": <0-10 how strongly it solves a real everyday problem>,
  "demo3s": <true if the benefit can be shown in a 3-second video>,
  "upsell": <0-10 bundle / upsell / accessory potential>,
  "brandable": <0-10 potential to brand, customise or improve packaging>,
  "ip_risk": "none" | "low" | "high"   (high = copies a famous brand, character or patented design),
  "restricted": <true for weapons, drugs, supplements making medical claims, adult, tobacco/vapes, counterfeit>,
  "fragile_heavy": <true if glass/ceramic, liquid, battery-heavy or > 2 kg>,
  "seasonal": <true if it only sells in one season/holiday>,
  "est_cost_usd": <typical AliExpress/1688 unit cost in USD incl. cheap shipping, number>}}

Only ads that sell ONE specific physical product count. Use "product": null when the ad is:
- an app, game, software, website, SaaS, AI tool or online service
- a catalog / dynamic product ad whose text is a template placeholder in double curly braces
- a course, coaching, ebook, webinar, event, membership, subscription box or info product
- a local business or service (restaurant, salon, clinic, gym, cleaning, real estate, travel, car dealer)
- finance, insurance, crypto, loans, jobs, recruiting, education, charity, politics, news, media, music
- food, drinks, groceries or meal delivery; medicines or supplements
- a store-wide sale, a catalogue, a brand campaign or an ad showing several different products
- a general fashion/clothing/shoe/jewellery store (no single hero item)
- a giveaway, contest, creator/influencer content, entertainment or a meme with nothing to buy
- too vague to know what single item is sold
When in doubt, use null. Use the SAME key for the same product across ads.

Ads:
{ads}
"""


def _ad_line(i: int, ad: AdRecord) -> str:
    text = (ad.ad_text or "").replace("\n", " ")[:280]
    url = ad.landing_url or ""
    return json.dumps({"i": i, "platform": ad.platform, "advertiser": ad.advertiser_name,
                       "text": text, "url": url[:150]}, ensure_ascii=False)


async def ai_guesses(ads: list[AdRecord], batch: int = 40) -> dict[int, Optional[ProductGuess]]:
    out: dict[int, Optional[ProductGuess]] = {}
    for start in range(0, len(ads), batch):
        chunk = ads[start:start + batch]
        lines = "\n".join(_ad_line(start + j, ad) for j, ad in enumerate(chunk))
        result = _unwrap_list(await llm_json(SYSTEM, PROMPT.format(ads=lines)))
        if not isinstance(result, list):
            continue
        for row in result:
            if not isinstance(row, dict) or "i" not in row:
                continue
            idx = int(row["i"])
            if not row.get("product"):
                out[idx] = None
                continue
            key = slugify(row.get("key") or row["product"]) or slugify(row["product"])
            if not key:
                out[idx] = None
                continue
            cost = row.get("est_cost_usd")
            out[idx] = ProductGuess(
                key=key,
                name=str(row["product"]).strip().title(),
                category=row.get("category"),
                est_cost_usd=float(cost) if isinstance(cost, (int, float)) and cost > 0 else None,
                attributes={
                    "wow": row.get("wow"), "problem": row.get("problem"), "demo3s": row.get("demo3s"),
                    "upsell": row.get("upsell"), "brandable": row.get("brandable"),
                    "ip_risk": row.get("ip_risk", "none"), "restricted": bool(row.get("restricted")),
                    "fragile_heavy": bool(row.get("fragile_heavy")), "seasonal": bool(row.get("seasonal")),
                    "physical": True,
                },
            )
    return out


async def guess_products_detailed(ads: list[AdRecord]) -> list[tuple[Optional[ProductGuess], bool]]:
    """(guess or None, decided_by_ai) per ad, same order.

    Only the AI can say "this is not a product". A miss (no AI key and no
    heuristic hit, or an AI batch that failed) just means "can't tell yet" —
    the ad stays unlinked and is looked at again on the next run.
    """
    if not llm_available():
        # Free mode (no AI key): best-effort guesses from store URLs / titles.
        return [(heuristic_guess(ad), False) for ad in ads]
    ai = await ai_guesses(ads)
    # With an AI key, only the AI creates products: an ad it didn't answer for
    # (failed batch) stays unlinked and is retried next run — guesswork could
    # turn a non-product ad into a "product".
    return [(ai[i], True) if i in ai else (None, False) for i in range(len(ads))]


async def guess_products(ads: list[AdRecord]) -> list[Optional[ProductGuess]]:
    """One guess (or None) per ad, same order."""
    return [g for g, _ in await guess_products_detailed(ads)]


def cluster_keys(guesses: list[Optional[ProductGuess]], existing: list[str]) -> list[Optional[ProductGuess]]:
    """Rewrite each guess.key onto an existing/earlier key when near-identical."""
    known = list(existing)
    for g in guesses:
        if g is None:
            continue
        hit = match_existing(g.key, known)
        if hit:
            g.key = hit
        else:
            known.append(g.key)
    return guesses
