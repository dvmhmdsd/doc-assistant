"""Unit tests for :class:`PdfParser` (T024)."""
from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF

from src.parsers.pdf import PdfParser


def _write_pdf(path: Path, pages: list[str]) -> None:
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        if text:
            page.insert_text((72, 72), text)
    doc.save(str(path))
    doc.close()


def test_yields_one_segment_per_non_empty_page(tmp_path: Path) -> None:
    p = tmp_path / "three.pdf"
    _write_pdf(p, ["page 1", "page 2", "page 3"])

    segments = PdfParser().parse(str(p))

    assert len(segments) == 3
    assert [s.page_number for s in segments] == [1, 2, 3]
    assert all("page" in s.text for s in segments)


def test_skips_blank_pages(tmp_path: Path) -> None:
    p = tmp_path / "mixed.pdf"
    _write_pdf(p, ["page 1", "", "page 3"])

    segments = PdfParser().parse(str(p))

    assert [s.page_number for s in segments] == [1, 3]


def test_scan_only_pdf_returns_empty(tmp_path: Path) -> None:
    p = tmp_path / "blank.pdf"
    _write_pdf(p, ["", ""])

    assert PdfParser().parse(str(p)) == []


def test_char_offsets_are_monotonic(tmp_path: Path) -> None:
    p = tmp_path / "mono.pdf"
    _write_pdf(p, [f"text on page {i}." for i in range(1, 4)])

    segments = PdfParser().parse(str(p))

    starts = [s.char_start for s in segments]
    ends = [s.char_end for s in segments]
    assert starts == sorted(starts)
    assert all(s < e for s, e in zip(starts, ends, strict=True))
