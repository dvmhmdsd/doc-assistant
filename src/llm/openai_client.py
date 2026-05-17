"""OpenAI LLM client. Streams chat completion deltas.

Connection-open is wrapped in :func:`open_with_retry` (bounded retry +
``provider_retry_total`` increment). Mid-stream errors propagate without
re-attempt — we cannot replay an in-flight token stream.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

import structlog
from openai import AsyncOpenAI

from .base import ChatMessage, LLMClient
from .retry import open_with_retry

_log = structlog.get_logger(__name__)


class OpenAILLMClient(LLMClient):
    def __init__(
        self,
        api_key: str,
        model_name: str,
        client: AsyncOpenAI | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required for OpenAILLMClient")
        self._client = client or AsyncOpenAI(api_key=api_key)
        self._model = model_name

    @property
    def model_name(self) -> str:
        return self._model

    async def stream_chat(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        payload = [{"role": m.role, "content": m.content} for m in messages]

        async def _open():
            return await self._client.chat.completions.create(
                stream=True, model=self._model, messages=payload
            )

        stream = await open_with_retry("openai", _open)
        async for event in stream:
            try:
                choice = event.choices[0]
            except (IndexError, AttributeError):
                continue
            delta = getattr(choice, "delta", None)
            content = getattr(delta, "content", None) if delta is not None else None
            if content:
                yield content
