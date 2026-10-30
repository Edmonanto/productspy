"""One product as a Shopify product-import CSV ("Add to Shopify" button).

The user downloads the file and uploads it in Shopify → Products → Import.
The product comes in as a DRAFT so nothing goes on sale before they check it:
title, description, suggested price, cost per item, our stored photo (a
durable URL Shopify copies on import), category tags.

The description is written once by the AI (short, benefit-led, no brand names
or made-up specs) and cached on the product; without an AI key a plain
template is used. Columns follow Shopify's product CSV template.
"""
from __future__ import annotations

import csv
import html
import io
import json
import math
import re
from typing import Any, Optional

from app import db

from .llm import llm_available, llm_json

COLUMNS = [
    "Handle", "Title", "Body (HTML)", "Vendor", "Product Category", "Type", "Tags", "Published",
    "Option1 Name", "Option1 Value", "Variant SKU", "Variant Grams", "Variant Inventory Tracker",
    "Variant Inventory Qty", "Variant Inventory Policy", "Variant Fulfillment Service", "Variant Price",
    "Variant Compare At Price", "Variant Requires Shipping", "Variant Taxable", "Image Src",
    "Image Position", "Image Alt Text", "Gift Card", "SEO Title", "SEO Description", "Cost per item", "Status",
]

SYSTEM = "You write e-commerce product copy. JSON only."
PROMPT = """Write Shopify product copy for this product: "{title}" (category: {category}).
Rules: no brand names, no invented specs, sizes, materials or certifications, no medical claims,
no fake reviews or urgency. Plain, benefit-led English.
Return JSON: {{"title": "<product title, max 60 chars>",
 "intro": "<1-2 sentences>",
 "benefits": ["<short benefit>", "<short benefit>", "<short benefit>", "<short benefit>"],
 "seo_description": "<max 155 chars>"}}"""


def handle(title: str) -> str:
    h = re.sub(r"[^a-z0-9]+", "-", (title or "product").lower()).strip("-")
    return (h or "product")[:80]


def suggested_price(price: Optional[float], cost: Optional[float]) -> Optional[float]:
    """What competitors charge; without it, 3x cost. Rounded to .99."""
    base = price if price else (cost * 3 if cost else None)
    if not base or base <= 0:
        return None
    return max(0.99, math.ceil(base) - 0.01)


def _copy_fallback(title: str) -> dict:
    return {"title": title, "intro": f"{title}.", "benefits": [], "seo_description": title[:155]}


async def product_copy(p: Any) -> dict:
    """AI copy cached in products.attributes.shopify_copy; template without AI."""
    attrs = p["attributes"] if isinstance(p["attributes"], dict) else json.loads(p["attributes"] or "{}")
    cached = attrs.get("shopify_copy")
    if isinstance(cached, dict) and cached.get("title"):
        return cached
    if not llm_available():
        return _copy_fallback(p["title"])
    res = await llm_json(SYSTEM, PROMPT.format(title=p["title"], category=p["category"] or "general"),
                         max_tokens=600, purpose="shopify-copy")
    if not isinstance(res, dict) or not isinstance(res.get("title"), str):
        return _copy_fallback(p["title"])
    copy = {
        "title": res["title"].strip()[:70] or p["title"],
        "intro": str(res.get("intro") or "").strip()[:400],
        "benefits": [str(b).strip()[:120] for b in (res.get("benefits") or []) if str(b).strip()][:5],
        "seo_description": str(res.get("seo_description") or "").strip()[:160],
    }
    await db.execute(
        "update products set attributes = coalesce(attributes, '{}'::jsonb) || jsonb_build_object('shopify_copy', $2::jsonb) "
        "where id = $1", p["id"], json.dumps(copy))
    return copy


def body_html(copy: dict) -> str:
    parts = [f"<p>{html.escape(copy['intro'])}</p>"] if copy.get("intro") else []
    if copy.get("benefits"):
        parts.append("<ul>" + "".join(f"<li>{html.escape(b)}</li>" for b in copy["benefits"]) + "</ul>")
    return "".join(parts)


def build_csv(p: Any, copy: dict) -> str:
    price = float(p["price_usd"]) if p["price_usd"] is not None else None
    cost = float(p["cost_usd"]) if p["cost_usd"] is not None else None
    sell = suggested_price(price, cost)
    title = copy.get("title") or p["title"]
    tags = ", ".join(t for t in ("ProductSpy", (p["category"] or "").replace("-", " ")) if t)
    row = {
        "Handle": handle(title), "Title": title, "Body (HTML)": body_html(copy),
        "Vendor": "", "Product Category": "", "Type": (p["category"] or "").replace("-", " ").title(),
        "Tags": tags, "Published": "FALSE",
        "Option1 Name": "Title", "Option1 Value": "Default Title", "Variant SKU": "",
        "Variant Grams": "", "Variant Inventory Tracker": "", "Variant Inventory Qty": "",
        "Variant Inventory Policy": "deny", "Variant Fulfillment Service": "manual",
        "Variant Price": f"{sell:.2f}" if sell else "", "Variant Compare At Price": "",
        "Variant Requires Shipping": "TRUE", "Variant Taxable": "TRUE",
        "Image Src": p["image_url"] or "", "Image Position": "1" if p["image_url"] else "",
        "Image Alt Text": title, "Gift Card": "FALSE",
        "SEO Title": title[:70], "SEO Description": copy.get("seo_description") or "",
        "Cost per item": f"{cost:.2f}" if cost else "", "Status": "draft",
    }
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLUMNS)
    w.writeheader()
    w.writerow(row)
    return buf.getvalue()
