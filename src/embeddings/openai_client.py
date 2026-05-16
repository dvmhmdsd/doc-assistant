"""OpenAI embedding provider backed by the official ``openai`` async SDK.

Batches inputs in groups of ``batch_size`` (default 100) to stay under
OpenAI's per-request limits and to keep retries scoped to small units.
Retry/backoff lives in :mod:`src.llm.retry` (T041) and is layered in by
the factory once that module lands.
"""
from __future__ import annotations

from openai import AsyncOpenAI

from .base import EmbeddingProvider

_DEFAULT_MODEL = "text-embedding-3-small"
_DEFAULT_BATCH_SIZE = 100
# Known fixed dims for OpenAI embedding models; lookup avoids guessing.
_KNOWN_DIMS: dict[str, int] = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        api_key: str,
        model_name: str = _DEFAULT_MODEL,
        batch_size: int = _DEFAULT_BATCH_SIZE,
        client: AsyncOpenAI | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required for OpenAIEmbeddingProvider")
        self._model_name = model_name
        self._batch_size = batch_size
        self._client = client or AsyncOpenAI(api_key=api_key)
        self._dimensions: int | None = _KNOWN_DIMS.get(model_name)

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimensions(self) -> int:
        if self._dimensions is None:
            raise RuntimeError(
                "dimensions unknown for model "
                f"{self._model_name!r} — call `embed` at least once first"
            )
        return self._dimensions

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        out: list[list[float]] = []
        for i in range(0, len(texts), self._batch_size):
            batch = texts[i : i + self._batch_size]
            response = await self._client.embeddings.create(
                model=self._model_name, input=batch
            )
            # OpenAI guarantees response.data ordering matches request order.
            out.extend([item.embedding for item in response.data])

        if out and self._dimensions is None:
            self._dimensions = len(out[0])
        return out
