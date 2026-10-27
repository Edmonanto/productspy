"""Second look before a product is shown: do its ads really sell it?

Extraction names each ad on its own, then near-identical names are merged.
That can put an ad under the wrong product ("LED strip" vs "LED mirror"), or
keep a store-wide promo ad under a product. Before picks are made, the top
candidates go through one more AI check: the product name plus every ad
grouped under it, and the question "which of these ads advertise exactly this
product?". Ads that don't are taken off the product (and not counted again),
the product is rescored on the ads that remain, and the product photo is
taken from the ad that best shows it.

Results are remembered per ad (attributes.verified_ads), so an ad is only
checked once; a product is only re-checked when new ads join it.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from .collectors.base import AdRecord
from .llm import llm_available, llm_json

log = logging.getLogger("winners")

MAX_ADS_PER_CHECK = 15
CANDIDATES = 40          # how many top products get checked per run

SYSTEM = (
    "You are a meticulous e-commerce analyst. You check whether ads really advertise a given "
    "physical product. You answer with strict JSON only."
)

PROMPT = """Product: "{name}"

Below are ads that were grouped under this product. For EACH ad decide if it clearly
advertises this exact product (same kind of item; any brand, store or wording is fine).
Say false for: a different product, a store-wide sale or several products at once,
an app, game, software, service, course, event, food, supplement, local business,
creator content with nothing to buy, or text too vague to tell.

Also say whether "{name}" itself is ONE physical product that an online store ships
(false for apps, services, courses, food, supplements, "store", "collection", "sale", etc.).

Return JSON:
{{"is_product": true | false,
  "matches": [<i of every ad that advertises this product>],
  "best": <i of the ad that shows the product most clearly, or null>,
  "name": "<the product's generic name in English, 2-5 words, no brand>" or null}}

Ads:
{ads}
"""


def ad_key(ad: AdRecord) -> str:
    return f"{ad.platform}:{ad.external_id}"


@dataclass
class Verdict:
    keep: list[AdRecord] = field(default_factory=list)
    reject: list[AdRecord] = field(default_factory=list)
    best: Optional[AdRecord] = None
    name: Optional[str] = None
    checked: bool = False          # False = AI unavailable / failed: nothing changes
    verified: bool = False         # every ad of the product has passed the check (now or before)
    not_product: bool = False      # the AI says the "product" itself isn't a physical product


def _line(i: int, ad: AdRecord) -> str:
    return json.dumps({
        "i": i, "platform": ad.platform, "advertiser": ad.advertiser_name,
        "text": (ad.ad_text or "").replace("\n", " ")[:300],
        "url": (ad.landing_url or "")[:150],
    }, ensure_ascii=False)


async def verify_product(name: str, ads: list[AdRecord], already_ok: set[str]) -> Verdict:
    """Check the not-yet-verified ads of one product."""
    todo = [a for a in ads if ad_key(a) not in already_ok]
    known = [a for a in ads if ad_key(a) in already_ok]
    if not todo:
        return Verdict(keep=list(ads), verified=bool(ads))
    if not llm_available():
        return Verdict(keep=list(ads))

    keep, reject, best, new_name, checked = list(known), [], None, None, False
    failed = not_product = False
    for start in range(0, len(todo), MAX_ADS_PER_CHECK):
        chunk = todo[start:start + MAX_ADS_PER_CHECK]
        res = await llm_json(SYSTEM, PROMPT.format(
            name=name, ads="\n".join(_line(i, a) for i, a in enumerate(chunk))), max_tokens=2000)
        if not isinstance(res, dict) or not isinstance(res.get("matches"), list):
            keep += chunk                      # no answer: leave these ads as they were
            failed = True
            continue
        checked = True
        if res.get("is_product") is False:
            not_product = True
        ok = {int(i) for i in res["matches"] if isinstance(i, (int, float)) or str(i).isdigit()}
        for i, ad in enumerate(chunk):
            (keep if i in ok else reject).append(ad)
        b = res.get("best")
        if best is None and isinstance(b, (int, float)) and int(b) in ok and 0 <= int(b) < len(chunk):
            best = chunk[int(b)]
        if not new_name and isinstance(res.get("name"), str) and res["name"].strip():
            new_name = res["name"].strip()[:80].title()
    return Verdict(keep=keep, reject=reject, best=best, name=new_name, checked=checked,
                   verified=checked and not failed, not_product=not_product)
