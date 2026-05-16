"""Ingestion service facade (T048).

Pipeline: parse → chunk → embed → store. Each stage's timing is recorded
in ``doc_assistant_ingest_seconds``. The caller (the ``/upload`` route)
owns the temp file lifecycle; this service does NOT delete it.

Raises typed :class:`AppError` subclasses so the FastAPI handler renders
the OpenAPI ``Error`` shape:
  - :class:`UnsupportedMediaType` from ``parser_for`` for non-PDF/DOCX.
  - :class:`BadRequest` (``EmptyDocumentError``) when the parser yields
    nothing (e.g., scan-only PDFs).
  - :class:`BadRequest` on parser exceptions, preserving the cause.
"""
from __future__ import annotations

import asyncio
import hashlib
import time
from typing import TypedDict

from ..api.errors import BadRequest
from ..chunker.chunker import Chunker
from ..embeddings.base import EmbeddingProvider
from ..observability.metrics import ingest_seconds
from ..parsers.factory import parser_for
from ..vector_store.base import VectorStore


class EmptyDocumentError(BadRequest):
    code = "bad_request"

    def __init__(self, message: str = "uploaded document contains no extractable text") -> None:
        super().__init__(message)


class IngestionResult(TypedDict):
    document_id: str
    chunk_count: int
    page_count: int | None
    parse_ms: int
    chunk_ms: int
    embed_ms: int
    store_ms: int
    total_ms: int


class IngestionService:
    def __init__(
        self,
        chunker: Chunker,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
    ) -> None:
        self._chunker = chunker
        self._embedder = embedding_provider
        self._store = vector_store

    async def ingest(
        self,
        *,
        file_path: str,
        filename: str,
        mime_type: str | None,
        session_id: str,
    ) -> IngestionResult:
        total_start = time.perf_counter()
        parser = parser_for(filename, mime_type)  # raises UnsupportedMediaType

        parse_start = time.perf_counter()
        try:
            segments = await asyncio.to_thread(parser.parse, file_path)
        except (FileNotFoundError, PermissionError) as exc:
            raise BadRequest("failed to read uploaded document") from exc
        except ValueError as exc:
            raise BadRequest("failed to parse uploaded document") from exc
        parse_ms = int((time.perf_counter() - parse_start) * 1000)

        if not segments:
            raise EmptyDocumentError()

        # Deterministic document_id from file bytes — same file uploaded
        # twice yields the same id (idempotent re-ingest).
        document_id = await asyncio.to_thread(_sha256_of_file, file_path)

        chunk_start = time.perf_counter()
        chunks = self._chunker.chunk(segments, document_id=document_id, session_id=session_id)
        chunk_ms = int((time.perf_counter() - chunk_start) * 1000)

        embed_start = time.perf_counter()
        embeddings = await self._embedder.embed([c.text for c in chunks])
        embed_ms = int((time.perf_counter() - embed_start) * 1000)

        store_start = time.perf_counter()
        await self._store.add(session_id=session_id, chunks=chunks, embeddings=embeddings)
        store_ms = int((time.perf_counter() - store_start) * 1000)

        total_ms = int((time.perf_counter() - total_start) * 1000)
        ingest_seconds.observe(total_ms / 1000.0)

        page_numbers = {s.page_number for s in segments if s.page_number is not None}
        return IngestionResult(
            document_id=document_id,
            chunk_count=len(chunks),
            page_count=len(page_numbers) if page_numbers else None,
            parse_ms=parse_ms,
            chunk_ms=chunk_ms,
            embed_ms=embed_ms,
            store_ms=store_ms,
            total_ms=total_ms,
        )


def _sha256_of_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()
