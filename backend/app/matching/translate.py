"""Translate supplier titles to English so they can be matched.

1688 titles are Chinese and keyword-stuffed — 猫窝保暖防寒窝小型犬狗狗贝壳冬天
半封闭式秋季垫子猫床保暖猫床 is a single "title". Literal translation carries
the stuffing across, so the model is asked for the *product descriptor* — the
nouns and attributes that identify the thing — which is what token matching
needs.

Titles never change, so each product is translated once and the result is
cached on the row. Calls are batched because per-product translation would
make a 50-product run 50 API calls.
"""
import json
import logging

from .. import config

log = logging.getLogger(__name__)

BATCH_SIZE = 40

SYSTEM = (
    "You convert Chinese e-commerce listing titles into short English product "
    "descriptors for keyword matching. These titles are keyword-stuffed: they "
    "repeat synonyms and cram in unrelated search terms. Return only the words "
    "that identify what the product actually IS — its noun and its "
    "distinguishing attributes (material, shape, function, target animal or "
    "person). Drop marketing filler, repeated synonyms, sizes and seasons. "
    "Aim for 3-8 words. If a title is already English, return it unchanged. "
    "If you cannot tell what the product is, return an empty string for it."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "translations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "english": {"type": "string"},
                },
                "required": ["id", "english"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["translations"],
    "additionalProperties": False,
}


async def translate_batch(items: list[tuple[str, str]]) -> dict[str, str]:
    """[(product_id, title)] -> {product_id: english}.

    Returns {} when translation is unavailable rather than raising: matching
    is an enhancement, and it must never take the ingestion run down with it.
    """
    if not items:
        return {}
    if not config.ANTHROPIC_API_KEY:
        log.info("matching: ANTHROPIC_API_KEY unset, skipping translation")
        return {}

    try:
        from anthropic import AsyncAnthropic
    except ImportError:
        log.warning("matching: anthropic package not installed")
        return {}

    client = AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
    results: dict[str, str] = {}

    try:
        for start in range(0, len(items), BATCH_SIZE):
            batch = items[start : start + BATCH_SIZE]
            listing = "\n".join(f"{pid}\t{title}" for pid, title in batch)

            try:
                message = await client.messages.create(
                    model=config.ANTHROPIC_MODEL,
                    # Thinking shares this budget with the reply, and a batch
                    # of 40 descriptors is not small — leave real headroom.
                    max_tokens=8000,
                    output_config={
                        "effort": "low",
                        "format": {"type": "json_schema", "schema": SCHEMA},
                    },
                    system=SYSTEM,
                    messages=[{
                        "role": "user",
                        "content": (
                            "Convert each line (id<TAB>title) to an English "
                            f"product descriptor:\n\n{listing}"
                        ),
                    }],
                )
            except Exception as exc:
                log.warning("matching: translation batch failed: %s", exc)
                continue

            if message.stop_reason == "refusal":
                log.warning("matching: translation batch refused")
                continue

            text = "".join(
                b.text for b in message.content if b.type == "text"
            ).strip()
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                log.warning("matching: translation returned non-JSON")
                continue

            for entry in payload.get("translations", []):
                pid, english = entry.get("id"), (entry.get("english") or "").strip()
                if pid and english:
                    results[pid] = english

            log.info(
                "matching: translated %d/%d titles in batch",
                len([e for e in payload.get("translations", []) if e.get("english")]),
                len(batch),
            )
    finally:
        await client.close()

    return results
