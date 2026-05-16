from __future__ import annotations

from abc import ABC, abstractmethod

from ..models.chunk import Chunk


class VectorStore(ABC):
    """Session-scoped vector store contract (Repository pattern).

    Implementations MUST partition by ``session_id``: a search in
    session A MUST NOT return chunks stored under session B (FR-018).
    ``search`` MUST return ``(Chunk, similarity)`` tuples ordered by
    **descending similarity** where similarity ∈ ``[0, 1]`` (larger =
    more similar). ``drop_session`` MUST be idempotent.
    """

    @abstractmethod
    async def add(
        self,
        session_id: str,
        chunks: list[Chunk],
        embeddings: list[list[float]],
    ) -> None: ...

    @abstractmethod
    async def search(
        self,
        session_id: str,
        query_embedding: list[float],
        k: int,
    ) -> list[tuple[Chunk, float]]: ...

    @abstractmethod
    async def drop_session(self, session_id: str) -> None: ...
