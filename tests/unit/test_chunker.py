import pytest

from src.parsers.base import ParsedSegment
from src.chunker.chunker import Chunker


def test_chunker_splits_and_overlaps_correctly():
    text = (
        "This is a test document. "
        "It contains multiple sentences and should be chunked into windows. "
        "The chunker must respect the requested overlap and maintain sequence indexes."
    )
    seg = ParsedSegment(text=text, page_number=1, section_path="/", char_start=0, char_end=len(text))

    chunker = Chunker(size_tokens=10, overlap_tokens=2)
    chunks = chunker.chunk([seg], document_id="d1", session_id="s1")

    assert len(chunks) >= 2

    for i, c in enumerate(chunks):
        assert c.sequence_index == i
        assert c.document_id == "d1"
        assert c.session_id == "s1"

    # verify coverage: fill a char buffer and ensure every position is covered by chunk text
    full_text = text
    buf = [None] * len(full_text)
    for c in chunks:
        assert 0 <= c.char_start < c.char_end <= len(full_text)
        slice_text = full_text[c.char_start:c.char_end]
        assert slice_text == c.text
        for i in range(c.char_start, c.char_end):
            buf[i] = full_text[i]

    reconstructed = ''.join(ch for ch in buf if ch is not None)
    assert reconstructed == full_text

