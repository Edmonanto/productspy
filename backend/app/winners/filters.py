"""Deterministic guard rails on top of the AI: things that are never a product.

The AI decides what an ad sells, but it can still let through an app, a
streaming "short drama", a design tool or a course. These rules are applied
whatever the AI said:

  * NON_PRODUCT words in the product name / category  -> not a physical product
  * NON_PRODUCT_ADVERTISERS (app & media brands)       -> their ads are never products
  * a product needs an image to be picked (the ad's own thumbnail is used
    when the store page gave none)
"""
from __future__ import annotations

import re

# Whole words / phrases that mean "not a physical product".
NON_PRODUCT_TERMS = [
    "app", "apps", "mobile app", "software", "saas", "web app", "browser extension", "plugin",
    "ai tool", "ai app", "ai assistant", "chatbot", "ai drama", "ai video", "ai photo", "ai editor", "ai generator",
    "template", "templates", "design tool", "photo editor", "video editor", "editing app",
    "drama", "dramas", "short drama", "mini drama", "episode", "episodes", "movies", "tv show", "tv series",
    "streaming service", "novels", "story app", "audiobook", "audiobooks", "podcast",
    "mobile game", "video game", "online game", "casino", "slots", "betting", "lottery", "sweepstakes",
    "course", "courses", "masterclass", "coaching", "mentorship", "webinar", "workshop",
    "ebook", "e-book", "printable", "digital download", "digital product",
    "subscription", "membership", "consultation", "agency",
    "insurance", "loan", "loans", "credit card", "mortgage", "crypto", "forex",
    "vpn", "web hosting", "domain name", "cloud storage", "dating app", "recruitment",
    "event tickets", "concert", "meal kit", "food delivery", "restaurant",
    "supplement", "supplements", "vitamins", "medication",
    "gift card", "voucher", "donation", "charity", "giveaway",
]

# App, media and service brands that advertise heavily but never sell a physical product.
NON_PRODUCT_ADVERTISERS = [
    "canva", "capcut", "chatgpt", "openai", "notion", "grammarly", "adobe", "figma", "picsart", "lightroom",
    "reelshort", "dramabox", "shortmax", "goodshort", "flextv", "dramawave", "netshort", "moboreels", "kalos tv",
    "topshort", "playlet", "minishort", "shorttv", "dreame", "goodnovel", "webnovel", "wattpad", "kindle",
    "netflix", "disney+", "hulu", "spotify", "audible", "youtube premium",
    "temu", "shein",
    "duolingo", "babbel", "coursera", "udemy", "skillshare", "masterclass", "headspace", "noom",
    "royal match", "candy crush", "monopoly go", "raid shadow", "whiteout survival", "last war", "royal kingdom",
    "tinder", "bumble", "hinge", "uber", "lyft", "doordash", "hellofresh", "booking.com", "airbnb", "expedia",
    "nordvpn", "expressvpn", "surfshark", "hostinger", "squarespace", "wix", "shopify", "godaddy",
]

_TERM_RX = re.compile(r"\b(" + "|".join(re.escape(t) for t in sorted(NON_PRODUCT_TERMS, key=len, reverse=True)) + r")\b", re.I)
_ADV_RX = re.compile(r"\b(" + "|".join(re.escape(t) for t in sorted(NON_PRODUCT_ADVERTISERS, key=len, reverse=True)) + r")\b", re.I)

# Never a physical product, whatever else the name says ("Meal Kit Subscription").
STRONG_TERMS = [
    "subscription", "membership", "drama", "dramas", "short drama", "episode", "episodes", "course", "courses",
    "masterclass", "coaching", "webinar", "ebook", "e-book", "insurance", "loan", "loans", "crypto", "casino",
    "betting", "lottery", "supplement", "supplements", "vitamins", "medication", "gift card", "donation",
    "charity", "meal kit", "food delivery", "audiobook", "podcast",
    "dog food", "cat food", "pet food", "fresh meals", "snacks", "groceries",
]
_STRONG_RX = re.compile(r"\b(" + "|".join(re.escape(t) for t in sorted(STRONG_TERMS, key=len, reverse=True)) + r")\b", re.I)

# Words that look like the terms above but name real products ("game controller", "phone stand").
PRODUCT_CONTEXT = re.compile(
    r"\b(controller|console|holder|stand|mount|case|cover|charger|cable|light|lamp|kit|board|toy|puzzle|"
    r"organizer|bag|bottle|brush|mat|pad|projector|speaker|headphones?|earbuds|keyboard|mouse|tablet|"
    r"plush|figure|tool kit|blocks|card game|board game|dice|chess|protector|pillow|bank|extension|"
    r"microphone|tripod|ring light|camera|printer|watch|band|strap|stick|gamepad|joystick|headset)\b", re.I)


def non_product_reason(title: str | None, category: str | None = None) -> str | None:
    """Why this product name can't be a physical product, or None."""
    text = " ".join(x for x in (title, category) if x)
    if not text.strip():
        return None
    strong = _STRONG_RX.search(text)
    if strong:
        return f"'{strong.group(1)}' — a service, media or digital item, not a physical product"
    context = PRODUCT_CONTEXT.search(text)
    adv = _ADV_RX.search(text)
    if adv and not context:
        return f"'{adv.group(1)}' is an app / service brand, not a product"
    m = _TERM_RX.search(text)
    if m and not context:
        return f"'{m.group(1)}' — an app, service, media or digital item, not a physical product"
    return None


def non_product_advertiser(name: str | None) -> bool:
    return bool(name and _ADV_RX.search(name))


# Facebook/Instagram catalog ads ("Advantage+ catalog", dynamic product ads) show
# a store's whole catalogue. The scraper sees the unfilled template —
# "{{product.name}} | {{product.brand}}" — so the text names no product, and
# identical template text would otherwise merge unrelated stores into one
# "product". They are never treated as a single-product ad.
_TEMPLATE_RX = re.compile(r"\{\{\s*[\w.\-]+\s*\}\}|\{\{\s*product\.|\[\[\s*product\.", re.I)


def is_catalog_template(text: str | None) -> bool:
    return bool(text and _TEMPLATE_RX.search(text))


# ── names too vague to be ONE product ───────────────────────────────────────
# "Necklace", "Kitchen Gadget", "Skin Care Product": a bucket, not a product.
# Ads for a heart pendant, a promise necklace and a letter necklace all land
# in it, so its ad count, score and photo describe several different items —
# the result is wrong. Such names are never picked.
VAGUE_HEADS = {
    "gadget", "gadgets", "product", "products", "item", "items", "accessory", "accessories",
    "essentials", "finds", "stuff", "thing", "things", "bundle", "collection", "gift", "gifts",
    "set", "kit", "jewelry", "jewellery", "clothing", "apparel", "decor", "tool", "tools",
    "device", "devices", "supplies", "goods", "merch",
}
BROAD_SINGLE = {
    "necklace", "bracelet", "ring", "rings", "earrings", "pendant", "watch", "dress", "shirt", "shoes",
    "sneakers", "bag", "handbag", "toy", "toys", "skincare", "makeup", "cosmetics", "perfume", "lamp",
    "light", "case", "charger", "speaker", "headphones", "earbuds", "furniture", "bedding", "pillow",
    "blanket", "cream", "serum", "food", "clothes", "hoodie", "leggings", "jacket", "sunglasses",
}


def too_vague(title: str | None) -> bool:
    """True when a product name is a category rather than one item."""
    words = re.findall(r"[a-z]+", (title or "").lower())
    if not words:
        return True
    if words[-1] in VAGUE_HEADS:
        return True
    return len(words) == 1 and words[0] in BROAD_SINGLE
