"""LLMClient contract — every implementation must yield multiple deltas.

The retry-policy half of the contract (≤2 retries on transient errors,
budget enforced, non-transient surfaces immediately) lives in
``test_retry_policy.py`` and is exercised against the policy directly
(it is policy-level, not per-client).
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest

from src.llm.base import ChatMessage, LLMClient


class _FakeLLMClient(LLMClient):
    """Deterministic stub yielding token deltas with a small sleep between."""

    def __init__(self, model_name: str = "fake") -> None:
        self._model = model_name

    @property
    def model_name(self) -> str:
        return self._model

    async def stream_chat(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        for token in ["Hello", " ", "world", "!"]:
            await asyncio.sleep(0)
            yield token


async def _collect(client: LLMClient) -> list[str]:
    out: list[str] = []
    async for delta in client.stream_chat([ChatMessage(role="user", content="hi")]):
        out.append(delta)
    return out


@pytest.mark.asyncio
async def test_stream_chat_yields_multiple_deltas() -> None:
    deltas = await _collect(_FakeLLMClient())
    assert len(deltas) > 1
    assert "".join(deltas) == "Hello world!"


@pytest.mark.asyncio
async def test_stream_chat_emits_first_delta_before_completion() -> None:
    """First delta MUST arrive before the stream finishes (incremental)."""
    client = _FakeLLMClient()
    stream = client.stream_chat([ChatMessage(role="user", content="hi")])
    first = await anext(stream)
    assert first == "Hello"
    remaining = [d async for d in stream]
    assert remaining == [" ", "world", "!"]
