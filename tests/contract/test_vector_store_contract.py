"""VectorStore contract — every impl (in-memory test fake + Chroma) passes.

Parametrising over both impls is what makes this a real contract test:
the production :class:`ChromaVectorStore` and the test :class:`_InMemory`
fake walk through the same assertions. Add new impls to ``_FACTORIES``.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Callable

import pytest

from src.models.chunk import Chunk
from src.vector_store.base import VectorStore
from src.vector_store.chroma import ChromaVectorStore


# ---- a minimal in-memory fake (cosine similarity) ------------------

class _InMemoryVectorStore(VectorStore):
    def __init__(self) -> None:
        self._data: dict[str, list[tuple[Chunk, list[float]]]] = {}

    async def add(self, session_id, chunks, embeddings):
        rows = self._data.setdefault(session_id, [])
        for c, e in zip(chunks, embeddings, strict=True):
            rows.append((c, e))

    async def search(self, session_id, query_embedding, k):
        rows = self._data.get(session_id, [])
        qn = math.sqrt(sum(x * x for x in query_embedding)) or 1.0
        scored: list[tuple[Chunk, float]] = []
        for c, e in rows:
            en = math.sqrt(sum(x * x for x in e)) or 1.0
            sim = sum(a * b for a, b in zip(query_embedding, e, strict=True)) / (qn * en)
            scored.append((c, max(0.0, float(sim))))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]

    async def drop_session(self, session_id):
        self._data.pop(session_id, None)


def _in_memory_factory(_tmp: Path) -> VectorStore:
    return _InMemoryVectorStore()


def _chroma_factory(tmp: Path) -> VectorStore:
    return ChromaVectorStore(persist_directory=str(tmp / "chroma"))


_FACTORIES: list[Callable[[Path], VectorStore]] = [_in_memory_factory, _chroma_factory]


# ---- helpers --------------------------------------------------------

def _chunk(session_id: str, idx: int) -> Chunk:
    return Chunk(
        chunk_id=f"doc1:{idx}",
        document_id="doc1",
        session_id=session_id,
        sequence_index=idx,
        text=f"chunk {idx}",
        page_number=idx + 1,
        section_path=None,
        char_start=idx * 10,
        char_end=idx * 10 + 5,
    )


# ---- contract suite -------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("factory", _FACTORIES)
async def test_add_then_search_returns_stored_chunks(
    factory: Callable[[Path], VectorStore], tmp_path: Path
) -> None:
    store = factory(tmp_path)
    chunks = [_chunk("s", 0), _chunk("s", 1)]
    await store.add("s", chunks, [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]])

    results = await store.search("s", [1.0, 0.0, 0.0, 0.0], k=2)
    assert len(results) >= 1
    assert any(c.chunk_id == "doc1:0" for c, _ in results)


@pytest.mark.asyncio
@pytest.mark.parametrize("factory", _FACTORIES)
async def test_search_returns_similarity_in_unit_range(
    factory: Callable[[Path], VectorStore], tmp_path: Path
) -> None:
    store = factory(tmp_path)
    chunks = [_chunk("s", 0)]
    await store.add("s", chunks, [[1.0, 0.0, 0.0, 0.0]])

    results = await store.search("s", [1.0, 0.0, 0.0, 0.0], k=1)
    assert results, "expected at least one hit"
    _, score = results[0]
    # Identical vectors → similarity == 1 (modulo numerical noise).
    assert 0.0 <= score <= 1.0001  # allow tiny float overshoot


@pytest.mark.asyncio
@pytest.mark.parametrize("factory", _FACTORIES)
async def test_session_isolation_per_fr018(
    factory: Callable[[Path], VectorStore], tmp_path: Path
) -> None:
    store = factory(tmp_path)
    await store.add("a", [_chunk("a", 0)], [[1.0, 0.0, 0.0, 0.0]])
    await store.add("b", [_chunk("b", 0)], [[1.0, 0.0, 0.0, 0.0]])

    res_a = await store.search("a", [1.0, 0.0, 0.0, 0.0], k=10)
    assert all(c.session_id == "a" for c, _ in res_a)
    assert all(c.document_id == "doc1" for c, _ in res_a)


@pytest.mark.asyncio
@pytest.mark.parametrize("factory", _FACTORIES)
async def test_drop_session_is_idempotent(
    factory: Callable[[Path], VectorStore], tmp_path: Path
) -> None:
    store = factory(tmp_path)
    await store.add("s", [_chunk("s", 0)], [[1.0, 0.0, 0.0, 0.0]])
    await store.drop_session("s")
    await store.drop_session("s")  # second call must not raise


@pytest.mark.asyncio
@pytest.mark.parametrize("factory", _FACTORIES)
async def test_search_after_drop_returns_empty(
    factory: Callable[[Path], VectorStore], tmp_path: Path
) -> None:
    store = factory(tmp_path)
    await store.add("s", [_chunk("s", 0)], [[1.0, 0.0, 0.0, 0.0]])
    await store.drop_session("s")
    assert await store.search("s", [1.0, 0.0, 0.0, 0.0], k=5) == []
