"""Claude call returning parsed JSON, using the official anthropic SDK.

Used by extract.py to name the product behind each ad. Returns None when no
key is configured or the call fails — the caller then falls back to the
URL/title heuristic rather than failing the run.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from app import config

log = logging.getLogger(__name__)


def llm_available() -> bool:
    return bool(config.ANTHROPIC_API_KEY)


def extract_json(text: str) -> Any:
    """Pull the first JSON array/object out of a reply (tolerates ``` fences)."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    for opener, closer in (("[", "]"), ("{", "}")):
        start, end = text.find(opener), text.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except ValueError:
                continue
    return json.loads(text)


async def llm_json(system: str, prompt: str, max_tokens: int = 8000) -> Any | None:
    if not config.ANTHROPIC_API_KEY:
        return None
    try:
        from anthropic import AsyncAnthropic
    except ImportError:
        log.warning("anthropic package not installed; using heuristics")
        return None

    client = AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
    try:
        message = await client.messages.create(
            model=config.WINNERS_MODEL,
            max_tokens=max_tokens,
            # Classification, not reasoning — keep thinking short so the reply
            # isn't squeezed out of max_tokens.
            output_config={"effort": "low"},
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:
        log.warning("winners extraction call failed, using heuristics: %s", exc)
        return None
    finally:
        await client.close()

    if message.stop_reason == "refusal":
        log.warning("winners extraction refused")
        return None
    text = "".join(b.text for b in message.content if b.type == "text")
    try:
        return extract_json(text)
    except ValueError:
        log.warning("winners extraction returned non-JSON: %s", text[:200])
        return None
