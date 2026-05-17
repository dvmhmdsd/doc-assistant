"""Local sentence-transformers embedding provider.

CPU-bound model inference is offloaded to a worker thread via
``asyncio.to_thread`` so the FastAPI event loop is not blocked on the
request path (constitution Principle IV).
"""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, cast

from .base import EmbeddingProvider

if TYPE_CHECKING:  # pragma: no cover - typing-only import
    from sentence_transformers import SentenceTransformer

_DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
_DEFAULT_BATCH_SIZE = 64


class LocalEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        model_name: str = _DEFAULT_MODEL,
        batch_size: int = _DEFAULT_BATCH_SIZE,
    ) -> None:
        self._model_name = model_name
        self._batch_size = batch_size
        self._model: SentenceTransformer | None = None
        self._dimensions: int | None = None
        self._load_lock = asyncio.Lock()

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimensions(self) -> int:
        """Return the embedding dimensionality.

        Raises ``RuntimeError`` if accessed before any call to :meth:`embed`
        (no synchronous model load — that would deadlock on the FastAPI
        event loop). Callers that need the dimension up front should
        ``await provider.embed([""])`` once at startup.
        """
        if self._dimensions is None:
            raise RuntimeError(
                "dimensions unknown — call `embed` at least once before querying"
            )
        return self._dimensions

    async def _ensure_model(self) -> SentenceTransformer:
        if self._model is not None:
            return self._model
        async with self._load_lock:
            cached = self._model
            if cached is not None:
                return cached

            def _load() -> SentenceTransformer:
                from sentence_transformers import SentenceTransformer

                return cast("SentenceTransformer", SentenceTransformer(self._model_name))

            model = await asyncio.to_thread(_load)
            self._model = model
            dim = model.get_sentence_embedding_dimension()
            if dim is None:
                raise RuntimeError(
                    f"sentence-transformers model {self._model_name!r} reported no dimension"
                )
            self._dimensions = int(dim)
            return model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = await self._ensure_model()

        def _encode(batch: list[str]) -> list[list[float]]:
            vectors = model.encode(batch, show_progress_bar=False, convert_to_numpy=True)
            return [[float(v) for v in row] for row in vectors]

        out: list[list[float]] = []
        for i in range(0, len(texts), self._batch_size):
            batch = texts[i : i + self._batch_size]
            out.extend(await asyncio.to_thread(_encode, batch))
        return out
