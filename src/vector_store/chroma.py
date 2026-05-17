"""ChromaDB-backed :class:`VectorStore` — one collection per session.

Per-session collection isolates documents (FR-018). Cosine distance is
forced via collection metadata so similarity ranking matches what the
sentence/OpenAI embedding models were trained for. Search returns
``(Chunk, similarity)`` where similarity ∈ ``[0, 1]`` with **larger =
more similar** — distances from Chroma are converted before being
exposed so downstream callers (``QAService``, ``Citation.score``) can
order chunks by descending score per the interface contract.
"""
from __future__ import annotations

import asyncio
import hashlib
from typing import Any, Final

import chromadb
from chromadb.api.models.Collection import Collection

from ..models.chunk import Chunk
from .base import VectorStore

_COSINE_METRIC: Final[dict[str, str]] = {"hnsw:space": "cosine"}


class ChromaVectorStore(VectorStore):
    def __init__(self, persist_directory: str) -> None:
        self._client = chromadb.PersistentClient(path=persist_directory)
        # Per-session locks guard the first-create race for a new session.
        self._locks: dict[str, asyncio.Lock] = {}

    @staticmethod
    def _collection_name(session_id: str) -> str:
        """Return the on-disk collection name for ``session_id``.

        Hashing keeps the raw, unguessable session handle off disk while
        still producing a stable, valid Chroma collection identifier.
        """
        digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:16]
        return f"session_{digest}"

    async def _collection_for(self, session_id: str) -> Collection:
        lock = self._locks.setdefault(session_id, asyncio.Lock())
        async with lock:
            return await asyncio.to_thread(
                self._client.get_or_create_collection,
                name=self._collection_name(session_id),
                metadata=_COSINE_METRIC,
            )

    async def add(
        self,
        session_id: str,
        chunks: list[Chunk],
        embeddings: list[list[float]],
    ) -> None:
        if not chunks:
            return
        if len(chunks) != len(embeddings):
            raise ValueError(
                f"chunks/embeddings length mismatch: {len(chunks)} vs {len(embeddings)}"
            )

        collection = await self._collection_for(session_id)
        await asyncio.to_thread(
            collection.add,
            ids=[c.chunk_id for c in chunks],
            embeddings=embeddings,  # type: ignore[arg-type]
            documents=[c.text for c in chunks],
            metadatas=[self._chunk_metadata(c) for c in chunks],
        )

    async def search(
        self,
        session_id: str,
        query_embedding: list[float],
        k: int,
    ) -> list[tuple[Chunk, float]]:
        if k <= 0:
            return []

        collection = await self._collection_for(session_id)
        result = await asyncio.to_thread(
            collection.query,
            query_embeddings=[query_embedding],  # type: ignore[arg-type]
            n_results=k,
            include=["distances", "metadatas", "documents"],
        )

        ids = result["ids"][0]
        if not ids:
            return []
        distances_field = result["distances"]
        metadatas_field = result["metadatas"]
        documents_field = result["documents"]
        assert distances_field is not None
        assert metadatas_field is not None
        assert documents_field is not None
        distances = distances_field[0]
        metadatas = metadatas_field[0]
        documents = documents_field[0]

        out: list[tuple[Chunk, float]] = []
        for cid, distance, metadata, document in zip(
            ids, distances, metadatas, documents, strict=True
        ):
            # Cosine distance ∈ [0, 2]; map to similarity ∈ [0, 1] so the
            # caller can order by descending score per the contract.
            similarity = max(0.0, 1.0 - float(distance))
            out.append(
                (
                    self._chunk_from_metadata(session_id, cid, document, dict(metadata)),
                    similarity,
                )
            )
        return out

    async def drop_session(self, session_id: str) -> None:
        name = self._collection_name(session_id)

        def _drop() -> None:
            try:
                self._client.delete_collection(name)
            except chromadb.errors.NotFoundError:
                # Idempotent per the VectorStore contract.
                pass

        await asyncio.to_thread(_drop)
        # Free the per-session lock; subsequent reuse of the same id is
        # legal (session ended + a new one happening to collide is fine).
        self._locks.pop(session_id, None)

    # ---- helpers ------------------------------------------------------

    @staticmethod
    def _chunk_metadata(chunk: Chunk) -> dict[str, Any]:
        """Build the metadata dict, omitting locator keys when absent.

        Chroma stores ``None`` literally; downstream metadata filters
        cannot reliably express "page_number IS NULL", so we drop the
        key entirely when no locator is available.
        """
        metadata: dict[str, Any] = {
            "chunk_id": chunk.chunk_id,
            "document_id": chunk.document_id,
            "session_id": chunk.session_id,
            "sequence_index": chunk.sequence_index,
            "char_start": chunk.char_start,
            "char_end": chunk.char_end,
        }
        if chunk.page_number is not None:
            metadata["page_number"] = chunk.page_number
        if chunk.section_path is not None:
            metadata["section_path"] = chunk.section_path
        return metadata

    @staticmethod
    def _chunk_from_metadata(
        session_id: str,
        chunk_id: str,
        document: str,
        metadata: dict[str, Any],
    ) -> Chunk:
        return Chunk(
            chunk_id=str(metadata.get("chunk_id", chunk_id)),
            document_id=str(metadata["document_id"]),
            session_id=session_id,
            sequence_index=int(metadata["sequence_index"]),
            text=document,
            page_number=(
                int(metadata["page_number"]) if "page_number" in metadata else None
            ),
            section_path=(
                str(metadata["section_path"]) if "section_path" in metadata else None
            ),
            char_start=int(metadata["char_start"]),
            char_end=int(metadata["char_end"]),
        )
