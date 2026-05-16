from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List
from dataclasses import dataclass


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
    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Return embeddings for the input texts, preserving order."""
        raise NotImplementedError()
