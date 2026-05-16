from __future__ import annotations

import re
from typing import List, Optional, Sequence

from ..parsers.base import ParsedSegment
from src.models.chunk import Chunk


class SimpleTokenizer:
    """A very small tokenizer that yields token text and character spans.

    This is a fallback tokenizer used for tests. It tokenizes on non-whitespace
    runs (regex '\\S+'). In production we can swap in a `tiktoken`-based tokenizer
    that only counts tokens but for precise char-span mapping this approach is used.
    """

    _tok_re = re.compile(r"\S+")

    def tokenize_with_spans(self, text: str) -> list[tuple[str, int, int]]:
        return [(m.group(0), m.start(), m.end()) for m in self._tok_re.finditer(text)]


class Chunker:
    def __init__(self, size_tokens: int, overlap_tokens: int, tokenizer: Optional[SimpleTokenizer] = None):
        if size_tokens <= 0:
            raise ValueError("size_tokens must be > 0")
        if overlap_tokens < 0:
            raise ValueError("overlap_tokens must be >= 0")
        if overlap_tokens >= size_tokens:
            raise ValueError("overlap_tokens must be < size_tokens")

        self.size_tokens = size_tokens
        self.overlap_tokens = overlap_tokens
        self.tokenizer = tokenizer or SimpleTokenizer()

    def chunk(self, segments: Sequence[ParsedSegment], *, document_id: str, session_id: str) -> List[Chunk]:
        """Token-aware chunking.

        - Joins segments with a double newline separator to avoid token-merge across
          segment boundaries.
        - Tokenizes the full text and produces windows of `size_tokens` with
          `overlap_tokens` overlap.
        - Determines dominant segment for each chunk by maximum character overlap.
        - Produces deterministic `chunk_id` as `{document_id}:{sequence_index}`.
        """
        if not segments:
            return []

        sep = "\n\n"
        full_text_parts: List[str] = []
        segment_ranges: List[tuple[int, int, ParsedSegment]] = []
        cursor = 0
        for idx, seg in enumerate(segments):
            text = seg.text or ""
            if idx > 0:
                # add separator between segments
                full_text_parts.append(sep)
                cursor += len(sep)
            start = cursor
            full_text_parts.append(text)
            cursor += len(text)
            end = cursor
            segment_ranges.append((start, end, seg))

        full_text = "".join(full_text_parts)
        if not full_text:
            return []

        tokens_with_spans = self.tokenizer.tokenize_with_spans(full_text)
        if not tokens_with_spans:
            return []

        token_spans = [(s, e) for (_tok, s, e) in tokens_with_spans]

        chunks: List[Chunk] = []
        seq = 0
        step = self.size_tokens - self.overlap_tokens
        if step <= 0:
            raise ValueError("size_tokens must be greater than overlap_tokens")

        i = 0
        n_tokens = len(token_spans)
        while i < n_tokens:
            window_tokens = token_spans[i : min(i + self.size_tokens, n_tokens)]
            char_start = window_tokens[0][0]
            char_end = window_tokens[-1][1]
            chunk_text = full_text[char_start:char_end]

            # pick dominant segment by char overlap
            best_seg = None
            best_overlap = 0
            for sstart, send, seg in segment_ranges:
                ov = min(char_end, send) - max(char_start, sstart)
                if ov > best_overlap:
                    best_overlap = ov
                    best_seg = seg

            page_number = best_seg.page_number if best_seg is not None else None
            section_path = best_seg.section_path if best_seg is not None else None

            chunk = Chunk(
                chunk_id=f"{document_id}:{seq}",
                document_id=document_id,
                session_id=session_id,
                sequence_index=seq,
                text=chunk_text,
                page_number=page_number,
                section_path=section_path,
                char_start=char_start,
                char_end=char_end,
            )
            chunks.append(chunk)
            seq += 1

            if i + self.size_tokens >= n_tokens:
                break
            i += step

        return chunks

