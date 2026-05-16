"""Unit tests for the citation formatter (T027)."""
from __future__ import annotations

from src.models.chunk import Chunk
from src.services.prompts import format_citations, locator_for


def _chunk(*, page: int | None, section: str | None) -> Chunk:
    return Chunk(
        chunk_id="d1:0",
        document_id="d1",
        session_id="s1",
        sequence_index=0,
        text="t",
        page_number=page,
        section_path=section,
        char_start=0,
        char_end=1,
    )


def test_pdf_chunk_locator_is_page_n() -> None:
    assert locator_for(_chunk(page=3, section=None)) == "page 3"


def test_docx_chunk_locator_is_section_path() -> None:
    assert locator_for(_chunk(page=None, section="Title > Section A")) == "Title > Section A"


def test_chunk_with_no_locator_falls_back_to_unknown() -> None:
    assert locator_for(_chunk(page=None, section=None)) == "unknown"


def test_format_citations_emits_openapi_shape_with_score() -> None:
    chunk = _chunk(page=3, section=None)
    out = format_citations([(chunk, 0.87)])
    assert out == [
        {
            "chunk_id": "d1:0",
            "document_id": "d1",
            "locator": "page 3",
            "score": 0.87,
        }
    ]


def test_format_citations_preserves_order() -> None:
    a, b = _chunk(page=1, section=None), _chunk(page=2, section=None)
    out = format_citations([(a, 0.9), (b, 0.4)])
    assert [c["locator"] for c in out] == ["page 1", "page 2"]
    assert [c["score"] for c in out] == [0.9, 0.4]
