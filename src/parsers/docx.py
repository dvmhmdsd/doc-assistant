"""DOCX parser backed by ``python-docx``.

Walks the document body in order. Maintains a heading-level stack so each
emitted :class:`ParsedSegment` carries a ``section_path`` like
``"Article 5 > §2"`` for citation (FR-007a). Also walks tables so content
inside tables (common in legal agreements: signature blocks, schedules)
is not dropped.
"""
from __future__ import annotations

from docx import Document
from docx.document import Document as _DocumentT
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from .base import DocumentParser, ParsedSegment


def _heading_level(paragraph: Paragraph) -> int | None:
    """Return the heading level (1-based) for a paragraph, or None."""
    style_name = (paragraph.style.name or "").strip() if paragraph.style is not None else ""
    if style_name.startswith("Heading "):
        try:
            return int(style_name.removeprefix("Heading "))
        except ValueError:
            return None
    if style_name in {"Title", "Subtitle"}:
        return 1
    return None


def _iter_body_blocks(document: _DocumentT):
    """Yield paragraphs and tables in document order."""
    body = document.element.body
    for child in body.iterchildren():
        tag = child.tag
        if tag == qn("w:p"):
            yield Paragraph(child, document)
        elif tag == qn("w:tbl"):
            yield Table(child, document)


def _section_path(stack: list[tuple[int, str]]) -> str | None:
    return " > ".join(title for _, title in stack) if stack else None


class DocxParser(DocumentParser):
    def parse(self, file_path: str) -> list[ParsedSegment]:
        document = Document(file_path)
        heading_stack: list[tuple[int, str]] = []  # [(level, title), ...]
        segments: list[ParsedSegment] = []
        cursor = 0

        def emit(text: str) -> None:
            nonlocal cursor
            if not text.strip():
                return
            start = cursor
            cursor += len(text)
            segments.append(
                ParsedSegment(
                    text=text,
                    page_number=None,
                    section_path=_section_path(heading_stack),
                    char_start=start,
                    char_end=cursor,
                )
            )

        for block in _iter_body_blocks(document):
            if isinstance(block, Paragraph):
                level = _heading_level(block)
                if level is not None:
                    # New heading: pop deeper/equal-level entries, push this one.
                    while heading_stack and heading_stack[-1][0] >= level:
                        heading_stack.pop()
                    heading_stack.append((level, block.text.strip()))
                emit(block.text)
            elif isinstance(block, Table):
                for row in block.rows:
                    for cell in row.cells:
                        for paragraph in cell.paragraphs:
                            emit(paragraph.text)

        return segments
