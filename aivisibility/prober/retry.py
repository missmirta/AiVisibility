"""Small hand-rolled retry-with-backoff helper shared by both probers.

No extra dependency (e.g. tenacity) — the logic is simple enough to own.
"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


async def with_retry(
    coro_factory: Callable[[], Awaitable[T]],
    max_attempts: int = 3,
    base_delay: float = 1.0,
    retry_on: tuple[type[Exception], ...] = (Exception,),
) -> T:
    """Call coro_factory(), retrying on exponential backoff.

    Only exceptions matching `retry_on` are retried — anything else (e.g. an
    invalid API key or a malformed request) propagates immediately instead of
    burning through max_attempts on a failure retrying can't fix.
    Re-raises the last exception once attempts are exhausted."""
    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return await coro_factory()
        except retry_on as exc:
            last_exc = exc
            if attempt < max_attempts - 1:
                await asyncio.sleep(base_delay * (2**attempt))
    assert last_exc is not None
    raise last_exc
