"""Prompt + citation helpers (T046).

System prompt mandates grounding in the provided context (FR-007). The
user-prompt builder interleaves retrieved chunks with citation tags so
the model can attribute its answers. ``format_citations`` emits the
``event: citations`` SSE payload matching the OpenAPI Citation schema.
"""
from __future__ import annotations

from collections.abc import Iterable

from ..models.chunk import Chunk

SYSTEM_PROMPT = (
    "You are a helpful assistant that answers questions strictly from the provided "
    "document context. If the answer is not contained in the provided context, "
    "reply 'I don't know.' Do not fabricate facts. When you use a passage from the "
    "context, cite it with its [CITATION id=...] tag."
)


def locator_for(chunk: Chunk) -> str:
    """Return the human-readable locator for a chunk's citation."""
    if chunk.page_number is not None:
        return f"page {chunk.page_number}"
    if chunk.section_path:
        return chunk.section_path
    return "unknown"


def build_user_prompt(question: str, retrieved: Iterable[Chunk]) -> str:
    parts: list[str] = [f"Question: {question}", "", "Context:"]
    for chunk in retrieved:
        parts.append(f"[CITATION id={chunk.chunk_id} locator={locator_for(chunk)}]")
        parts.append(chunk.text)
        parts.append("")
    parts.append("Answer using ONLY the context. If unknown, say 'I don't know.'")
    return "\n".join(parts)


def format_citations(chunks_with_scores: Iterable[tuple[Chunk, float]]) -> list[dict]:
    """Build the OpenAPI ``Citation`` payload for the SSE ``citations`` frame.

    Schema (per ``contracts/openapi.yaml``):
        {chunk_id, document_id, locator, score}
    """
    return [
        {
            "chunk_id": chunk.chunk_id,
            "document_id": chunk.document_id,
            "locator": locator_for(chunk),
            "score": float(score),
        }
        for chunk, score in chunks_with_scores
    ]
