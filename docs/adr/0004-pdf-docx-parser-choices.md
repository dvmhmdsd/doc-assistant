# ADR 0004: PDF and DOCX Parser Choices (PyMuPDF + python-docx)

## Status

Accepted — 2026-05-16.

## Context

Legal-tech reviewers (the primary user) upload contracts as PDF or
DOCX. The assistant must:

- extract text faithfully enough to support natural-language QA;
- emit a **page number** for PDF chunks and a **section path** for
  DOCX chunks so each citation has a human-readable locator (FR-007a);
- complete ingestion of a 50-page PDF in under 30 seconds on
  laptop-class hardware (SC-001);
- stay aligned with the constitution's "minimal dependency footprint"
  rule — every new runtime dep needs a rationale.

The parsers are the Strategy implementations behind the
`DocumentParser` ABC defined in `contracts/interfaces.md`.

## Decision

Use **PyMuPDF (`fitz`)** for PDF and **`python-docx`** for DOCX.

PDF (`src/parsers/pdf.py`):

- Open via `with fitz.open(...)`; iterate pages 1-based.
- One `ParsedSegment` per non-empty page with `page_number=i`,
  `section_path=None`.
- Empty pages skipped; a scan-only PDF (no extractable text) yields
  `[]` so the ingestion service can raise `EmptyDocumentError`.

DOCX (`src/parsers/docx.py`):

- Walk `doc.element.body` via `qn("w:p")` / `qn("w:tbl")` to preserve
  the original order of paragraphs and tables.
- Maintain a heading-level stack so each emitted `ParsedSegment`
  carries a `section_path` like `"Agreement > Article 1"`.
- Walk table cells (legal contracts often put schedules and signature
  blocks in tables — dropping them is content loss).

## Alternatives Considered

**`pdfminer.six`.** Pure Python, robust, well documented. Rejected
because it is materially slower than PyMuPDF on every PDF in our test
fixtures, and its locator helpers are thinner.

**`pdfplumber`.** Built on top of pdfminer; nicer high-level API and
table-extraction helpers. Slower than PyMuPDF. We do not need
structured table extraction in v1 — body text plus a locator is
enough.

**`unstructured` / `docling`.** Capable but heavyweight. Each pulls
multiple model files, OCR engines, and (for `docling`) PyTorch. They
contradict the minimal-deps rule and would make ingestion downloads
dominate first-run time.

**Apache Tika.** Mature, language-agnostic, handles everything.
Rejected outright because it requires a JVM, which our deployment
story (single Python image) cannot accept.

## Consequences

**Positive.** PyMuPDF is C-backed and consistently the fastest pure-text
extractor among popular open-source choices — well inside the 30-second
SC-001 budget for a 50-page PDF. We get page numbers for free (no
heuristics), so the PDF citation locator `"page N"` is exact.
`python-docx` is dependency-free Python and ergonomic; the heading-stack
section_path is computed in a few lines and gives DOCX citations real
information ("Agreement > Article 5 > §2") instead of useless
ordinals.

**Negative.** Scan-only PDFs are not supported — we return an empty
extraction and surface `EmptyDocumentError` to the user. Adding OCR
(Tesseract or otherwise) is a future extension, not v1 scope.
`python-docx` does not see content inside text boxes or some
WordprocessingML drawing elements; we accept that gap and document it
in the spec assumptions.

PyMuPDF is AGPL/commercial dual-licensed — for the demo / interview
context this is fine; a production deployment that ships the binary
would need a commercial license or a switch to a non-AGPL alternative
(pypdfium2, pdfplumber). Worth flagging here so the choice is not
silent.

## References

- `specs/001-doc-assistant-rag/research.md` — R-003.
- `specs/001-doc-assistant-rag/spec.md` — FR-001, FR-007a, SC-001.
- `src/parsers/pdf.py`, `src/parsers/docx.py`.
- `contracts/interfaces.md` — `DocumentParser` ABC.
