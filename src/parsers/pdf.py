"""PDF parser backed by PyMuPDF (``fitz``).

Emits one :class:`ParsedSegment` per non-empty page, with ``page_number``
set (1-based) so chunks built from these segments carry page-level
citation locators (FR-007a).
"""
from __future__ import annotations

import fitz  # PyMuPDF

from .base import DocumentParser, ParsedSegment


class PdfParser(DocumentParser):
    def parse(self, file_path: str) -> list[ParsedSegment]:
        segments: list[ParsedSegment] = []
        cursor = 0
        with fitz.open(file_path) as doc:
            for page_index, page in enumerate(doc, start=1):
                text = page.get_text()
                if not text:
                    continue
                start = cursor
                cursor += len(text)
                segments.append(
                    ParsedSegment(
                        text=text,
                        page_number=page_index,
                        section_path=None,
                        char_start=start,
                        char_end=cursor,
                    )
                )
        return segments
