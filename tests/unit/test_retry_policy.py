"""Unit tests for the bounded async retry policy (T041 / FR-021 / R-008)."""
from __future__ import annotations

import asyncio
import time

import httpx
import pytest

from src.api.errors import UpstreamUnavailable
from src.llm.retry import retryable
from src.observability.metrics import provider_retry_total


class _StubAPIStatusError(Exception):
    """Duck-types an SDK APIStatusError carrying a ``status_code`` attribute."""

    def __init__(self, status_code: int) -> None:
        super().__init__(f"http {status_code}")
        self.status_code = status_code


@pytest.mark.asyncio
async def test_retries_then_succeeds_on_transient() -> None:
    calls = {"n": 0}

    @retryable(provider="anthropic", max_wait=0.01, retry_budget_seconds=5.0)
    async def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.NetworkError("transient")
        return "ok"

    assert await flaky() == "ok"
    assert calls["n"] == 3  # 1 initial + 2 retries


@pytest.mark.asyncio
async def test_surfaces_upstream_unavailable_after_attempts_exhausted() -> None:
    @retryable(provider="anthropic", attempts=3, max_wait=0.01, retry_budget_seconds=5.0)
    async def always_503() -> None:
        raise _StubAPIStatusError(503)

    with pytest.raises(UpstreamUnavailable):
        await always_503()


@pytest.mark.asyncio
async def test_does_not_retry_non_transient() -> None:
    calls = {"n": 0}

    @retryable(provider="anthropic", max_wait=0.01, retry_budget_seconds=5.0)
    async def auth_failure() -> None:
        calls["n"] += 1
        raise _StubAPIStatusError(401)

    with pytest.raises(_StubAPIStatusError):
        await auth_failure()
    assert calls["n"] == 1  # No retry on 401.


@pytest.mark.asyncio
async def test_wall_clock_budget_enforced() -> None:
    @retryable(provider="anthropic", attempts=100, max_wait=0.01, retry_budget_seconds=0.05)
    async def slow_transient() -> None:
        # Sleep beyond the budget on every attempt.
        await asyncio.sleep(0.1)
        raise httpx.NetworkError("slow")

    start = time.monotonic()
    with pytest.raises(UpstreamUnavailable):
        await slow_transient()
    elapsed = time.monotonic() - start
    # Budget is 0.05s; allow a generous ceiling for CI jitter.
    assert elapsed < 1.0


@pytest.mark.asyncio
async def test_increments_provider_retry_total() -> None:
    before = provider_retry_total.labels(provider="openai")._value.get()  # type: ignore[attr-defined]

    @retryable(provider="openai", max_wait=0.01, retry_budget_seconds=5.0)
    async def two_retries_then_ok() -> str:
        if not hasattr(two_retries_then_ok, "n"):
            two_retries_then_ok.n = 0  # type: ignore[attr-defined]
        two_retries_then_ok.n += 1  # type: ignore[attr-defined]
        if two_retries_then_ok.n < 3:  # type: ignore[attr-defined]
            raise httpx.TimeoutException("slow")
        return "ok"

    assert await two_retries_then_ok() == "ok"
    after = provider_retry_total.labels(provider="openai")._value.get()  # type: ignore[attr-defined]
    # 2 retries = 2 increments via the before_sleep hook.
    assert after - before == 2


@pytest.mark.asyncio
async def test_retries_on_429() -> None:
    calls = {"n": 0}

    @retryable(provider="anthropic", max_wait=0.01, retry_budget_seconds=5.0)
    async def rate_limited() -> str:
        calls["n"] += 1
        if calls["n"] < 2:
            raise _StubAPIStatusError(429)
        return "ok"

    assert await rate_limited() == "ok"
    assert calls["n"] == 2
