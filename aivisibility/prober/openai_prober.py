"""OpenAI engine prober: plain chat completion, no tools/function calling.

Same neutral framing as the Claude prober — the query text is sent as the
only user message, nothing else, for a fair cross-engine comparison.
"""

import time

from openai import AsyncOpenAI

from ..common.config import OPENAI_MODEL, OPENAI_PRICING_PER_MTOK
from .base import ProbeResult
from .retry import with_retry

ENGINE = "openai"

_client = AsyncOpenAI()


def _estimate_cost(prompt_tokens: int, completion_tokens: int) -> float:
    prices = OPENAI_PRICING_PER_MTOK[OPENAI_MODEL]
    return (
        prompt_tokens * prices["input"] + completion_tokens * prices["output"]
    ) / 1_000_000


async def _call(query_text: str):
    return await _client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": query_text}],
    )


async def probe(query_text: str) -> ProbeResult:
    started = time.monotonic()
    result_text = ""
    prompt_tokens = None
    completion_tokens = None
    cost_usd = None
    error = None

    try:
        response = await with_retry(
            lambda: _call(query_text), max_attempts=3, base_delay=1.0
        )
        result_text = response.choices[0].message.content or ""
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        cost_usd = _estimate_cost(prompt_tokens, completion_tokens)
    except Exception as exc:  # noqa: BLE001 - reported as a stored error, not raised
        error = str(exc)

    latency_ms = int((time.monotonic() - started) * 1000)

    return ProbeResult(
        text=result_text,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        model=OPENAI_MODEL,
        error=error,
    )
