import pytest

from aivisibility.prober.retry import with_retry


async def test_returns_on_first_success():
    async def ok():
        return 7

    assert await with_retry(ok) == 7


async def test_retries_then_succeeds():
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("transient")
        return "done"

    assert await with_retry(flaky, max_attempts=3, base_delay=0) == "done"
    assert calls["n"] == 3


async def test_reraises_after_exhausting_attempts():
    calls = {"n": 0}

    async def always_fails():
        calls["n"] += 1
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await with_retry(always_fails, max_attempts=2, base_delay=0)
    assert calls["n"] == 2


async def test_non_retryable_exception_propagates_immediately():
    calls = {"n": 0}

    async def bad_request():
        calls["n"] += 1
        raise ValueError("bad")

    with pytest.raises(ValueError):
        await with_retry(bad_request, max_attempts=3, base_delay=0, retry_on=(RuntimeError,))
    assert calls["n"] == 1
