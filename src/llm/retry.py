"""Bounded async retry policy for provider calls (FR-021, R-008).

- ≤ 2 retries on transient errors (3 attempts total).
- Exponential backoff: multiplier=0.5, max=2 s.
- Total wall-clock budget enforced by ``asyncio.wait_for`` (default 5 s).
- Transient = ``httpx.TimeoutException``, ``httpx.NetworkError``, or provider
  ``APIStatusError`` with status in ``{429, 500, 502, 503, 504}``.
  Non-transient (other 4xx) surface immediately without retry.
- On retry, increments
  ``doc_assistant_provider_retry_total{provider="<name>"}`` (T008 / FR-023).
- Exhaustion (wall-clock or attempt cap) converts to typed
  :class:`UpstreamUnavailable` so the API surface (FR-011) renders the
  OpenAPI ``Error`` schema without leaking stack traces.
"""
from __future__ import annotations

import asyncio
import functools
from collections.abc import Awaitable, Callable
from typing import ParamSpec, TypeVar

import httpx
import structlog
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from ..api.errors import UpstreamUnavailable
from ..observability.metrics import provider_retry_total

P = ParamSpec("P")
T = TypeVar("T")

_TRANSIENT_STATUS: frozenset[int] = frozenset({429, 500, 502, 503, 504})
_log = structlog.get_logger(__name__)


def _is_transient(exc: BaseException) -> bool:
    """Return True iff ``exc`` matches the transient-error set in FR-021."""
    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)):
        return True
    # SDK exception classes that expose a `status_code` attribute (Anthropic +
    # OpenAI both subclass through their own APIStatusError types). Matching on
    # the duck-typed attribute keeps this module independent of the SDK choice.
    status = getattr(exc, "status_code", None)
    if isinstance(status, int) and status in _TRANSIENT_STATUS:
        return True
    return False


def retryable(
    provider: str,
    *,
    attempts: int = 3,
    max_wait: float = 2.0,
    retry_budget_seconds: float = 5.0,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Decorate an async function with the project's retry policy.

    ``provider`` is the metric label (``"anthropic"`` / ``"openai"``) for
    ``provider_retry_total``.
    """

    def _decorate(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @functools.wraps(func)
        async def _runner(*args: P.args, **kwargs: P.kwargs) -> T:
            async def _attempt() -> T:
                async for state in AsyncRetrying(
                    stop=stop_after_attempt(attempts),
                    wait=wait_exponential(multiplier=0.5, max=max_wait),
                    retry=retry_if_exception(_is_transient),
                    before_sleep=_before_sleep_factory(provider),
                ):
                    with state:
                        return await func(*args, **kwargs)
                # Unreachable — tenacity either returns or raises.
                raise RuntimeError("retry loop exited without value")

            try:
                return await asyncio.wait_for(_attempt(), timeout=retry_budget_seconds)
            except TimeoutError as exc:
                _log.warning(
                    "retry.budget_exhausted",
                    provider=provider,
                    budget_seconds=retry_budget_seconds,
                )
                raise UpstreamUnavailable(
                    f"{provider} call exceeded {retry_budget_seconds}s retry budget"
                ) from exc
            except RetryError as exc:
                # All attempts failed on transient errors before the budget ran out.
                raise UpstreamUnavailable(
                    f"{provider} call failed after {attempts} attempts"
                ) from exc.last_attempt.exception()

        return _runner

    return _decorate


def _before_sleep_factory(provider: str) -> Callable[[object], None]:
    """Tenacity ``before_sleep`` hook that bumps the retry counter."""

    def _hook(_retry_state: object) -> None:  # pragma: no cover - thin glue
        provider_retry_total.labels(provider=provider).inc()
        _log.info("retry.attempt", provider=provider)

    return _hook


async def open_with_retry(
    provider: str,
    opener: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    max_wait: float = 2.0,
    retry_budget_seconds: float = 5.0,
) -> T:
    """Open a streaming connection with the project's retry policy.

    The retry decorator above cannot wrap an ``async def f(): yield ...``
    function because calling such a function returns an async generator
    synchronously — ``await`` on it raises ``TypeError``. For streaming
    LLM clients we instead retry only the connection-open step (e.g.,
    ``manager.__aenter__()``); once the stream is established, iteration
    errors propagate normally.

    ``opener`` is a zero-arg callable returning an awaitable that resolves
    to the stream/handle to be consumed.
    """

    async def _attempt() -> T:
        async for state in AsyncRetrying(
            stop=stop_after_attempt(attempts),
            wait=wait_exponential(multiplier=0.5, max=max_wait),
            retry=retry_if_exception(_is_transient),
            before_sleep=_before_sleep_factory(provider),
        ):
            with state:
                return await opener()
        raise RuntimeError("retry loop exited without value")

    try:
        return await asyncio.wait_for(_attempt(), timeout=retry_budget_seconds)
    except TimeoutError as exc:
        _log.warning(
            "retry.budget_exhausted",
            provider=provider,
            budget_seconds=retry_budget_seconds,
        )
        raise UpstreamUnavailable(
            f"{provider} call exceeded {retry_budget_seconds}s retry budget"
        ) from exc
    except RetryError as exc:
        raise UpstreamUnavailable(
            f"{provider} call failed after {attempts} attempts"
        ) from exc.last_attempt.exception()
