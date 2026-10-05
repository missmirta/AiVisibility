"""Claude engine prober: plain user question, no tools, no web search.

Simulates what an ordinary user sees asking Claude directly, so the query
text is sent as-is with no extra framing. See docs/weeks/week2.md for the
Claude Agent SDK overhead caveat this prober carries.
"""

import time

from claude_agent_sdk import (
    ClaudeAgentOptions,
    CLIConnectionError,
    ProcessError,
    ResultMessage,
    query,
)

from ..common.config import CLAUDE_MODEL, MAX_BUDGET_USD_PER_CALL
from .base import ProbeResult
from .retry import with_retry

ENGINE = "claude"

# RuntimeError: our own signal for ResultMessage.is_error (often a transient
# API-side failure). CLIConnectionError/ProcessError: network or CLI-process
# failures. Anything else (e.g. CLIJSONDecodeError, MessageParseError — a
# protocol mismatch, not a transient failure) is not retried.
_RETRYABLE = (RuntimeError, CLIConnectionError, ProcessError)


async def _call(query_text: str) -> tuple[str, float | None, dict | None]:
    options = ClaudeAgentOptions(
        tools=[],
        model=CLAUDE_MODEL,
        system_prompt="",
        max_budget_usd=MAX_BUDGET_USD_PER_CALL,
    )
    result_text = ""
    cost_usd = None
    usage: dict | None = None
    error_msg = None

    async for message in query(prompt=query_text, options=options):
        if isinstance(message, ResultMessage):
            if message.is_error:
                error_msg = message.result or "unknown error"
            result_text = message.result or ""
            cost_usd = message.total_cost_usd
            usage = message.usage

    if error_msg is not None:
        raise RuntimeError(error_msg)
    return result_text, cost_usd, usage


async def probe(query_text: str) -> ProbeResult:
    started = time.monotonic()
    result_text = ""
    cost_usd = None
    usage: dict | None = None
    error = None

    try:
        result_text, cost_usd, usage = await with_retry(
            lambda: _call(query_text),
            max_attempts=3,
            base_delay=1.0,
            retry_on=_RETRYABLE,
        )
    except Exception as exc:  # noqa: BLE001 - reported as a stored error, not raised
        error = str(exc)

    latency_ms = int((time.monotonic() - started) * 1000)

    return ProbeResult(
        text=result_text,
        prompt_tokens=usage.get("input_tokens") if usage else None,
        completion_tokens=usage.get("output_tokens") if usage else None,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        model=CLAUDE_MODEL,
        error=error,
    )
