"""Shared result contract for engine probers (Claude, OpenAI, ...).

Both probers return this same shape so the storage layer does not need to
know which engine produced a result.
"""

from dataclasses import dataclass


@dataclass
class ProbeResult:
    text: str
    prompt_tokens: int | None
    completion_tokens: int | None
    cost_usd: float | None
    latency_ms: int
    model: str
    error: str | None = None
