from __future__ import annotations

from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    @property
    @abstractmethod
    def model_name(self) -> str:
        raise NotImplementedError()

    @property
    @abstractmethod
    def dimensions(self) -> int:
        raise NotImplementedError()

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return embeddings for the input texts, preserving order."""
        raise NotImplementedError()
