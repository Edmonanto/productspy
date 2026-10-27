"""LLM call returning parsed JSON: Claude (anthropic SDK) when
ANTHROPIC_API_KEY is set, otherwise any OpenAI-compatible API when
OPENAI_API_KEY is set.

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


def provider() -> str | None:
    if config.ANTHROPIC_API_KEY:
        return "anthropic"
    if config.OPENAI_API_KEY:
        return "openai"
    return None


def llm_available() -> bool:
    return provider() is not None


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


class LLMResult:
    """Parsed JSON (or None) plus token usage, for metering."""

    def __init__(self, data: Any = None, tokens_in: int = 0, tokens_out: int = 0,
                 model: str = "", error: str | None = None) -> None:
        self.data, self.tokens_in, self.tokens_out = data, tokens_in, tokens_out
        self.model, self.error = model, error


RETRY_STATUS = {408, 409, 429, 500, 502, 503, 504}


async def _openai_call(system: str, prompt: str, max_tokens: int, model: str) -> LLMResult:
    """OpenAI-compatible chat completion in JSON mode, with retries + backoff.

    JSON mode (response_format json_object) is asked for; a provider/reseller
    that rejects it is retried once without it.
    """
    import asyncio

    import httpx

    body: dict[str, Any] = {
        "model": model, "max_tokens": max_tokens, "temperature": 0,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
    }
    last_err = None
    async with httpx.AsyncClient(timeout=180) as client:
        for attempt in range(4):
            try:
                resp = await client.post(f"{config.OPENAI_BASE_URL}/chat/completions",
                                         headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"},
                                         json=body)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_err = f"network: {exc}"
                await asyncio.sleep(2 ** attempt)
                continue
            if resp.status_code == 400 and "response_format" in body and "response_format" in resp.text:
                body.pop("response_format")
                continue
            if resp.status_code in RETRY_STATUS:
                last_err = f"{resp.status_code} {resp.text[:200]}"
                await asyncio.sleep(min(20, 2 ** attempt * (3 if resp.status_code == 429 else 1)))
                continue
            if resp.status_code >= 300:
                return LLMResult(model=model, error=f"{resp.status_code} {resp.text[:300]}")
            data = resp.json()
            usage = data.get("usage") or {}
            text = (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""
            # JSON mode wraps a top-level array in an object; callers that want a
            # list get the first list value.
            try:
                parsed = extract_json(text)
            except ValueError:
                return LLMResult(model=model, error=f"non-JSON reply: {text[:200]}",
                                 tokens_in=usage.get("prompt_tokens", 0),
                                 tokens_out=usage.get("completion_tokens", 0))
            return LLMResult(parsed, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0), model)
    return LLMResult(model=model, error=last_err or "failed after retries")


async def _anthropic_call(system: str, prompt: str, max_tokens: int) -> LLMResult:
    try:
        from anthropic import AsyncAnthropic
    except ImportError:
        return LLMResult(error="anthropic package not installed")
    client = AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY, max_retries=3)
    try:
        message = await client.messages.create(
            model=config.WINNERS_MODEL, max_tokens=max_tokens,
            output_config={"effort": "low"}, system=system,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:
        return LLMResult(model=config.WINNERS_MODEL, error=str(exc)[:300])
    finally:
        await client.close()
    usage = getattr(message, "usage", None)
    tin, tout = (getattr(usage, "input_tokens", 0), getattr(usage, "output_tokens", 0)) if usage else (0, 0)
    if message.stop_reason == "refusal":
        return LLMResult(model=config.WINNERS_MODEL, error="refused", tokens_in=tin, tokens_out=tout)
    text = "".join(b.text for b in message.content if b.type == "text")
    try:
        return LLMResult(extract_json(text), tin, tout, config.WINNERS_MODEL)
    except ValueError:
        return LLMResult(model=config.WINNERS_MODEL, error=f"non-JSON reply: {text[:200]}",
                         tokens_in=tin, tokens_out=tout)


async def llm_call(system: str, prompt: str, max_tokens: int = 8000, purpose: str = "extract",
                   model: str | None = None) -> LLMResult:
    """One metered, capped LLM call returning parsed JSON in .data (None on failure)."""
    from app import usage

    which = provider()
    if which is None:
        return LLMResult(error="no AI key configured")
    if not await usage.allowed("llm"):
        return LLMResult(error="daily AI call cap reached")
    if which == "openai":
        res = await _openai_call(system, prompt, min(max_tokens, 16000), model or config.OPENAI_MODEL)
    else:
        res = await _anthropic_call(system, prompt, max_tokens)
    await usage.record("llm", purpose, ok=res.error is None, tokens_in=res.tokens_in,
                       tokens_out=res.tokens_out, error=res.error)
    if res.error:
        log.warning("LLM %s call failed: %s", purpose, res.error)
    return res


def _unwrap_list(data: Any) -> Any:
    """JSON mode returns an object; prompts that ask for an array get {"items": [...]}-style wrappers."""
    if isinstance(data, dict) and len(data) == 1:
        only = next(iter(data.values()))
        if isinstance(only, list):
            return only
    return data


async def llm_json(system: str, prompt: str, max_tokens: int = 8000, purpose: str = "extract") -> Any | None:
    res = await llm_call(system, prompt, max_tokens, purpose)
    if res.data is None:
        return None
    return res.data
