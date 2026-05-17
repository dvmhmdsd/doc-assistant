"""Anthropic LLM client. Streams token deltas via ``messages.stream``.

Connection-open is wrapped in :func:`open_with_retry` (bounded retry +
``provider_retry_total`` increment). Mid-stream errors propagate without
re-attempt — we cannot replay an in-flight token stream.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from anthropic import AsyncAnthropic

from .base import ChatMessage, LLMClient
from .retry import open_with_retry


class AnthropicLLMClient(LLMClient):
    def __init__(
        self,
        api_key: str,
        model_name: str,
        client: AsyncAnthropic | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required for AnthropicLLMClient")
        self._client = client or AsyncAnthropic(api_key=api_key)
        self._model = model_name

    @property
    def model_name(self) -> str:
        return self._model

    async def stream_chat(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        payload: list[dict[str, str]] = [
            {"role": m.role, "content": m.content} for m in messages
        ]
        manager = self._client.messages.stream(
            model=self._model,
            messages=payload,  # type: ignore[arg-type]
            max_tokens=4096,
        )

        # Retry the connection-open only; iteration runs without retry.
        stream = await open_with_retry("anthropic", manager.__aenter__)
        try:
            async for delta in stream.text_stream:
                if delta:
                    yield delta
        finally:
            await manager.__aexit__(None, None, None)
