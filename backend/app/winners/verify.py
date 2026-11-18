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
checked once; a product is only re-checked when new ads join it. The verdicts
carry a VERSION (attributes.verify_version): when the rules get stricter the
version goes up and every ad is checked again under the new rules.

Version 2 (2026-11-18): ads that didn't fit their product were reaching the
site ("Why doesn't every charger do this? Comment CABLE" under Portable
Charger, a jewellery brand's "Best Seller" ad under Promise Necklace). The
check was text-only and accepted anything in the same category. Now the AI
also SEES each ad's picture, must find this exact item in the ad (a related
item, a vague hook or a brand/store promo is a no), and says no when unsure.

Rejected ads that clearly sell ONE other real product ("other") are not thrown
away: they are named again on the next run and join the product they really
sell, so that product's score counts them (store.rehome_ads).
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from .collectors.base import AdRecord
from .llm import llm_available, llm_call, llm_json

log = logging.getLogger("winners")

VERSION = 2              # bump when the rules change: every ad is checked again
MAX_ADS_PER_CHECK = 8    # each ad's picture is sent along, so keep the batch small
CANDIDATES = 40          # how many top products get checked per run

SYSTEM = (
    "You are a meticulous e-commerce analyst. You check whether ads really advertise a given "
    "physical product. You answer with strict JSON only."
)

PROMPT = """Product: "{name}"

Below are ads that were grouped under this product. {pictures}
For EACH ad decide if it clearly advertises THIS EXACT product: the same specific item
(any brand, store or wording is fine). Be strict — customers open these ads to see the
product, so an ad that shows something else makes the whole page look wrong.

Say TRUE only when the text or the picture plainly shows or names this item.
Say FALSE for:
- a related but DIFFERENT item (a charging cable or a charging station is not a power bank;
  a bracelet is not a necklace; a fan is not a fan-light),
- a hook that never says what is sold ("Why doesn't every charger do this?", "you need this"),
- a brand or store promo, best-sellers, a sale, a restock or several products at once,
- an app, game, software, service, course, event, food, supplement or local business,
- creator content with nothing to buy,
- anything you are not sure about. When in doubt, say false.
If "{name}" is a broad category (e.g. "Necklace", "Kitchen Gadget"), keep only the ads that
show the same specific item as most of the ads, and give that item's specific name.

Also say whether "{name}" itself is ONE physical product that an online store ships
(false for apps, services, courses, food, supplements, "store", "collection", "sale", etc.).

Return JSON:
{{"is_product": true | false,
  "matches": [<i of every ad that advertises this product>],
  "other": [<i of every NON-matching ad that clearly sells ONE other physical product>],
  "best": <i of the ad that shows the product most clearly, or null>,
  "name": "<the specific item's generic name in English, 2-5 words, no brand, never a category>" or null}}

Ads:
{ads}
"""

PICTURES = ("The pictures attached are the ads' own images, in order: each ad line says which "
            "picture is its own (\"picture\": n), or null when it has none. Use the picture: "
            "the item it shows must be this product.")


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
    rehome: list[AdRecord] = field(default_factory=list)  # rejected, but sell another real product


def _line(i: int, ad: AdRecord, picture: Optional[int] = None) -> str:
    d = {
        "i": i, "platform": ad.platform, "advertiser": ad.advertiser_name,
        "text": (ad.ad_text or "").replace("\n", " ")[:300],
        "url": (ad.landing_url or "")[:150],
    }
    if picture is not None:
        d["picture"] = picture or None
    return json.dumps(d, ensure_ascii=False)


async def _picture(ad: AdRecord) -> Optional[bytes]:
    """The ad's own image as a small JPEG, or None (no link, expired, not an image)."""
    from .photos import download, shrink
    if not ad.thumbnail_url:
        return None
    got = await download(ad.thumbnail_url)
    return shrink(got[0]) if got else None


async def _ask(name: str, chunk: list[AdRecord]) -> object:
    """One AI check of a batch of ads, with their pictures when we can fetch them."""
    pics = await asyncio.gather(*(_picture(a) for a in chunk), return_exceptions=True)
    images: list[tuple[bytes, str]] = []
    numbers: list[int] = []
    for p in pics:
        if isinstance(p, (bytes, bytearray)) and p:
            images.append((bytes(p), "image/jpeg"))
            numbers.append(len(images))
        else:
            numbers.append(0)
    if not images:
        return await llm_json(SYSTEM, PROMPT.format(
            name=name, pictures="",
            ads="\n".join(_line(i, a) for i, a in enumerate(chunk))), max_tokens=2000, purpose="verify")
    res = await llm_call(SYSTEM, PROMPT.format(
        name=name, pictures=PICTURES,
        ads="\n".join(_line(i, a, numbers[i]) for i, a in enumerate(chunk))),
        max_tokens=2000, purpose="verify", images=images)
    return res.data


async def verify_product(name: str, ads: list[AdRecord], already_ok: set[str]) -> Verdict:
    """Check the not-yet-verified ads of one product."""
    from .filters import is_catalog_template
    templ = [a for a in ads if is_catalog_template(a.ad_text)]
    if templ:
        rest = [a for a in ads if not is_catalog_template(a.ad_text)]
        inner = await verify_product(name, rest, already_ok) if rest else Verdict(checked=True)
        inner.reject = templ + inner.reject
        inner.checked = True
        return inner
    todo = [a for a in ads if ad_key(a) not in already_ok]
    known = [a for a in ads if ad_key(a) in already_ok]
    if not todo:
        return Verdict(keep=list(ads), verified=bool(ads))
    if not llm_available():
        return Verdict(keep=list(ads))

    keep, reject, best, new_name, checked = list(known), [], None, None, False
    rehome: list[AdRecord] = []
    failed = not_product = False
    for start in range(0, len(todo), MAX_ADS_PER_CHECK):
        chunk = todo[start:start + MAX_ADS_PER_CHECK]
        res = await _ask(name, chunk)
        if not isinstance(res, dict) or not isinstance(res.get("matches"), list):
            keep += chunk                      # no answer: leave these ads as they were
            failed = True
            continue
        checked = True
        if res.get("is_product") is False:
            not_product = True
        ok = {int(i) for i in res["matches"] if isinstance(i, (int, float)) or str(i).isdigit()}
        other = {int(i) for i in (res.get("other") or [])
                 if isinstance(i, (int, float)) or str(i).isdigit()} - ok
        for i, ad in enumerate(chunk):
            (keep if i in ok else reject).append(ad)
            if i in other:
                rehome.append(ad)
        b = res.get("best")
        if best is None and isinstance(b, (int, float)) and int(b) in ok and 0 <= int(b) < len(chunk):
            best = chunk[int(b)]
        if not new_name and isinstance(res.get("name"), str) and res["name"].strip():
            new_name = res["name"].strip()[:80].title()
    return Verdict(keep=keep, reject=reject, best=best, name=new_name, checked=checked,
                   verified=checked and not failed, not_product=not_product, rehome=rehome)
