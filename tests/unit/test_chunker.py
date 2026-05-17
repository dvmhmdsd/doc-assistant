"""Unit tests for :class:`Chunker` (T023).

Uses the production :class:`TiktokenTokenizer` (``tiktoken`` is a hard
runtime dep — no try/skip).
"""
from __future__ import annotations

import pytest
import tiktoken

from src.chunker.chunker import Chunker, TiktokenTokenizer
from src.parsers.base import ParsedSegment

_ENC = tiktoken.get_encoding("cl100k_base")


def _segment(text: str, *, page: int | None = 1, section: str | None = None) -> ParsedSegment:
    return ParsedSegment(
        text=text,
        page_number=page,
        section_path=section,
        char_start=0,
        char_end=len(text),
    )


def test_chunk_ids_are_deterministic_sequence() -> None:
    chunker = Chunker(size_tokens=10, overlap_tokens=2)
    segments = [_segment("hello world. " * 50)]
    chunks = chunker.chunk(segments, document_id="d1", session_id="s1")
    assert [c.chunk_id for c in chunks] == [f"d1:{i}" for i in range(len(chunks))]


def test_chunk_size_respects_size_tokens() -> None:
    chunker = Chunker(size_tokens=20, overlap_tokens=4)
    segments = [_segment("alpha beta gamma delta " * 80)]
    chunks = chunker.chunk(segments, document_id="d", session_id="s")

    # Each chunk's text MUST encode to ≤ size_tokens tokens.
    for c in chunks:
        assert len(_ENC.encode(c.text)) <= 20


def test_chunks_overlap_by_overlap_tokens() -> None:
    chunker = Chunker(size_tokens=10, overlap_tokens=3)
    segments = [_segment("one two three four five six seven eight nine ten " * 5)]
    chunks = chunker.chunk(segments, document_id="d", session_id="s")
    assert len(chunks) >= 2

    # Adjacent chunks must share their last `overlap_tokens` of the previous
    # chunk with the first of the next.
    for prev, curr in zip(chunks, chunks[1:], strict=True):
        prev_tail_ids = _ENC.encode(prev.text)[-3:]
        curr_head_ids = _ENC.encode(curr.text)[:3]
        assert prev_tail_ids == curr_head_ids


def test_locator_carried_from_dominant_segment() -> None:
    chunker = Chunker(size_tokens=50, overlap_tokens=5)
    segments = [
        _segment("page one body. " * 30, page=1),
        _segment("page two body. " * 30, page=2),
    ]
    chunks = chunker.chunk(segments, document_id="d", session_id="s")

    # Every chunk inherits some non-None page_number.
    assert all(c.page_number is not None for c in chunks)


def test_empty_input_returns_empty_list() -> None:
    chunker = Chunker(size_tokens=10, overlap_tokens=2)
    assert chunker.chunk([], document_id="d", session_id="s") == []


def test_chunker_constructor_validates_args() -> None:
    with pytest.raises(ValueError):
        Chunker(size_tokens=0, overlap_tokens=0)
    with pytest.raises(ValueError):
        Chunker(size_tokens=10, overlap_tokens=-1)
    with pytest.raises(ValueError):
        Chunker(size_tokens=5, overlap_tokens=5)


def test_tokenizer_recovers_char_spans_for_ascii() -> None:
    tok = TiktokenTokenizer()
    text = "Hello, world! This is a test."
    spans = tok.tokenize_with_spans(text)
    assert spans, "expected at least one token span"
    # Reconstructing the spans should recover the original string.
    assert "".join(piece for piece, _, _ in spans) == text
    # Char spans monotonic + non-overlapping.
    for (_, _s1, e1), (_, s2, _) in zip(spans, spans[1:], strict=True):
        assert e1 == s2
