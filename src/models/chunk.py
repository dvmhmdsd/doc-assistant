from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    document_id: str
    session_id: str
    sequence_index: int
    text: str
    page_number: int | None
    section_path: str | None
    char_start: int
    char_end: int
