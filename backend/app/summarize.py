"""ai_summary generation via the Claude API.

One short call per product, run inside the ingestion worker rather than at
request time so the dashboard never waits on it. Summaries are only written
for products that don't have one, so a re-run costs nothing.
"""
import logging

from . import config
from .schemas import Product, Score

log = logging.getLogger(__name__)

SYSTEM = (
    "You write one-sentence assessments of dropshipping products for a "
    "product-research dashboard. Given a product and its computed scores, "
    "state plainly why it is or isn't worth selling: name the strongest "
    "signal and the biggest risk. No preamble, no bullet points, no "
    "marketing language. Maximum 30 words. If the data is too thin to judge, "
    "say so instead of inventing a rationale."
)


def _prompt(product: Product, score: Score) -> str:
    margin = None
    if product.price_usd and product.cost_usd:
        margin = round((product.price_usd - product.cost_usd) / product.price_usd * 100)

    return (
        f"Product: {product.title}\n"
        f"Category: {product.category or 'unknown'}\n"
        f"Source: {product.source}\n"
        f"Retail: {product.price_usd}  Cost: {product.cost_usd}  "
        f"Margin: {margin if margin is not None else 'unknown'}%\n"
        f"Scores — overall {score.overall_score}, demand {score.demand_score}, "
        f"margin {score.margin_score}, competition {score.competition_score} "
        f"(higher = less competition), trend {score.trend_score}\n"
        f"Advertisers seen: {sum(a.ad_count for a in product.ad_signals) or 'none'}"
    )


async def summarize(product: Product, score: Score) -> str:
    """Return a one-line assessment, or '' if summarisation is unavailable."""
    if not config.ANTHROPIC_API_KEY:
        return ""

    try:
        from anthropic import AsyncAnthropic
    except ImportError:
        log.warning("anthropic package not installed; skipping summaries")
        return ""

    client = AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
    try:
        message = await client.messages.create(
            model=config.ANTHROPIC_MODEL,
            max_tokens=2048,
            # Thinking is on by default and shares max_tokens with the reply,
            # so leave headroom above the ~30 words we actually want.
            output_config={"effort": "low"},
            system=SYSTEM,
            messages=[{"role": "user", "content": _prompt(product, score)}],
        )
    except Exception as exc:  # a summary is never worth failing ingestion over
        log.warning("summary failed for %s: %s", product.id, exc)
        return ""
    finally:
        await client.close()

    if message.stop_reason == "refusal":
        log.warning("summary refused for %s", product.id)
        return ""

    return "".join(
        block.text for block in message.content if block.type == "text"
    ).strip()
