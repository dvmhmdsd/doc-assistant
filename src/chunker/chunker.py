from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

import tiktoken

from ..models.chunk import Chunk
from ..parsers.base import ParsedSegment


class Tokenizer(ABC):
    """Tokenizer contract used by :class:`Chunker`.

    Implementations MUST return a list of ``(token_text, char_start, char_end)``
    tuples whose char ranges are non-overlapping, ordered, and addressable into
    the original ``text`` argument.
    """

    @abstractmethod
    def tokenize_with_spans(self, text: str) -> list[tuple[str, int, int]]: ...


class TiktokenTokenizer(Tokenizer):
    """Production tokenizer backed by tiktoken (default ``cl100k_base``).

    Chunk sizing in tokens matches the way downstream embedding/LLM models
    actually count tokens, so a ``size_tokens=500`` chunker reliably stays
    within those models' context windows (see research.md R-012).
    """

    def __init__(self, encoding_name: str = "cl100k_base") -> None:
        self._enc = tiktoken.get_encoding(encoding_name)
        self._encoding_name = encoding_name

    @property
    def encoding_name(self) -> str:
        return self._encoding_name

    def tokenize_with_spans(self, text: str) -> list[tuple[str, int, int]]:
        if not text:
            return []

        ids = self._enc.encode(text)
        if not ids:
            return []

        text_bytes = text.encode("utf-8")
        # Linear byte-offset -> char-offset map. Walk codepoints once.
        byte_to_char: list[int] = [0] * (len(text_bytes) + 1)
        char_idx = 0
        byte_idx = 0
        for ch in text:
            n = len(ch.encode("utf-8"))
            for k in range(n):
                byte_to_char[byte_idx + k] = char_idx
            byte_idx += n
            char_idx += 1
        byte_to_char[byte_idx] = char_idx

        spans: list[tuple[str, int, int]] = []
        byte_cursor = 0
        for tid in ids:
            piece_bytes = self._enc.decode_single_token_bytes(tid)
            start_b = byte_cursor
            end_b = byte_cursor + len(piece_bytes)
            char_start = byte_to_char[start_b]
            char_end = byte_to_char[end_b]
            piece = text[char_start:char_end]
            spans.append((piece, char_start, char_end))
            byte_cursor = end_b
        return spans


class Chunker:
    """Token-aware sliding-window chunker.

    - Concatenates ``ParsedSegment`` text with a ``"\\n\\n"`` separator so
      tokens never merge across logical segment boundaries.
    - Tokenizes the full text via the injected :class:`Tokenizer` (default
      :class:`TiktokenTokenizer` with ``cl100k_base``).
    - Emits chunks of at most ``size_tokens`` with ``overlap_tokens`` overlap.
    - Picks each chunk's locator (``page_number`` / ``section_path``) from
      the source segment with maximum character overlap with the chunk's
      char range.
    - ``chunk_id`` is deterministic: ``f"{document_id}:{sequence_index}"``.
    """

    def __init__(
        self,
        size_tokens: int = 500,
        overlap_tokens: int = 50,
        tokenizer: Tokenizer | None = None,
    ) -> None:
        if size_tokens <= 0:
            raise ValueError("size_tokens must be > 0")
        if overlap_tokens < 0:
            raise ValueError("overlap_tokens must be >= 0")
        if overlap_tokens >= size_tokens:
            raise ValueError("overlap_tokens must be < size_tokens")

        self.size_tokens = size_tokens
        self.overlap_tokens = overlap_tokens
        self.tokenizer: Tokenizer = tokenizer if tokenizer is not None else TiktokenTokenizer()

    def chunk(
        self,
        segments: Sequence[ParsedSegment],
        *,
        document_id: str,
        session_id: str,
    ) -> list[Chunk]:
        if not segments:
            return []

        sep = "\n\n"
        full_text_parts: list[str] = []
        segment_ranges: list[tuple[int, int, ParsedSegment]] = []
        cursor = 0
        for idx, seg in enumerate(segments):
            if idx > 0:
                full_text_parts.append(sep)
                cursor += len(sep)
            start = cursor
            full_text_parts.append(seg.text)
            cursor += len(seg.text)
            segment_ranges.append((start, cursor, seg))

        full_text = "".join(full_text_parts)
        if not full_text:
            return []

        token_spans = [(s, e) for _, s, e in self.tokenizer.tokenize_with_spans(full_text)]
        if not token_spans:
            return []

        step = self.size_tokens - self.overlap_tokens
        chunks: list[Chunk] = []
        n = len(token_spans)
        for seq, i in enumerate(range(0, n, step)):
            window = token_spans[i : i + self.size_tokens]
            char_start, char_end = window[0][0], window[-1][1]
            best_seg = self._dominant_segment(segment_ranges, char_start, char_end)
            chunks.append(
                Chunk(
                    chunk_id=f"{document_id}:{seq}",
                    document_id=document_id,
                    session_id=session_id,
                    sequence_index=seq,
                    text=full_text[char_start:char_end],
                    page_number=best_seg.page_number if best_seg else None,
                    section_path=best_seg.section_path if best_seg else None,
                    char_start=char_start,
                    char_end=char_end,
                )
            )
            if i + self.size_tokens >= n:
                break

        return chunks

    @staticmethod
    def _dominant_segment(
        ranges: list[tuple[int, int, ParsedSegment]],
        char_start: int,
        char_end: int,
    ) -> ParsedSegment | None:
        """Return the segment with maximum character overlap with [char_start, char_end)."""
        best_seg: ParsedSegment | None = None
        best_overlap = 0
        for sstart, send, seg in ranges:
            overlap = min(char_end, send) - max(char_start, sstart)
            if overlap > best_overlap:
                best_overlap = overlap
                best_seg = seg
        return best_seg
