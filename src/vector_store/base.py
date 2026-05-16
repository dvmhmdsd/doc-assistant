from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Tuple

from src.models.chunk import Chunk


class VectorStore(ABC):
    @abstractmethod
    async def add(self, session_id: str, chunks: List[Chunk], embeddings: List[List[float]]) -> None:
        raise NotImplementedError()

    @abstractmethod
    async def search(self, session_id: str, query_embedding: List[float], k: int) -> List[Tuple[Chunk, float]]:
        raise NotImplementedError()

    @abstractmethod
    async def drop_session(self, session_id: str) -> None:
        raise NotImplementedError()
