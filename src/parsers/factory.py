"""Parser factory — resolves a :class:`DocumentParser` from filename + MIME.

Raises :class:`UnsupportedMediaType` (HTTP 415) for anything outside
PDF/DOCX so the FastAPI exception handler renders the OpenAPI ``Error``
schema correctly without leaking stack traces (FR-001, FR-011).
"""
from __future__ import annotations

from ..api.errors import UnsupportedMediaType
from .base import DocumentParser
from .docx import DocxParser
from .pdf import PdfParser

_PDF_MIME = "application/pdf"
_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def parser_for(filename: str, mime_type: str | None = None) -> DocumentParser:
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    mt = (mime_type or "").lower()

    if mt == _PDF_MIME or ext == "pdf":
        return PdfParser()
    if mt == _DOCX_MIME or ext == "docx":
        return DocxParser()

    raise UnsupportedMediaType(f"unsupported file type: {filename!r} (mime={mime_type!r})")
