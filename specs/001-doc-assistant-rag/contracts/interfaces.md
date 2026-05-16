# Internal Interface Contracts

**Phase**: 1
**Branch**: `001-doc-assistant-rag`

Every cross-layer boundary in `src/` MUST go through one of the interfaces below
(constitution Principle I). Contract tests in `tests/contract/` parameterise over
implementations.

---

## 1. `DocumentParser` (Strategy pattern)

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass(frozen=True)
class ParsedSegment:
    text: str
    page_number: int | None     # PDF: 1-based; DOCX: None
    section_path: str | None    # DOCX: e.g. "Article 5 > §2"; PDF: None
    char_start: int             # offset in concatenated extracted text
    char_end: int

class DocumentParser(ABC):
    @abstractmethod
    def parse(self, file_path: str) -> list[ParsedSegment]: ...
```

**Contract**:

- `parse` is synchronous (CPU-bound; callers wrap in `run_in_threadpool`).
- Returned segments are in reading order; `char_start`/`char_end` are monotonically
  non-decreasing.
- Empty list = file had no extractable text (e.g., scan-only PDF). Caller surfaces
  the "not extractable" error.
- Implementations: `PdfParser` (PyMuPDF), `DocxParser` (python-docx).

---

## 2. `Chunker` (not an interface — single concrete; documented for completeness)

```python
@dataclass(frozen=True)
class Chunk:
    chunk_id: str               # f"{document_id}:{sequence_index}"
    document_id: str
    session_id: str
    sequence_index: int
    text: str
    page_number: int | None
    section_path: str | None
    char_start: int
    char_end: int

class Chunker:
    def __init__(self, size_tokens: int, overlap_tokens: int): ...
    def chunk(self, segments: list[ParsedSegment], *, document_id: str, session_id: str) -> list[Chunk]: ...
```

**Contract**:

- Each chunk's tokenized length ≤ `size_tokens`.
- Adjacent chunks overlap by `overlap_tokens`.
- Chunks inherit `page_number` / `section_path` from the dominant source segment
  (used for citations).

---

## 3. `EmbeddingProvider` (Strategy pattern)

```python
class EmbeddingProvider(ABC):
    @property
    @abstractmethod
    def model_name(self) -> str: ...

    @property
    @abstractmethod
    def dimensions(self) -> int: ...

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
```

**Contract**:

- Output length equals input length and preserves order.
- Each embedding has exactly `dimensions` floats.
- Implementations: `LocalEmbeddingProvider` (sentence-transformers, runs in a
  thread), `OpenAIEmbeddingProvider` (async via `AsyncOpenAI`).
- Failures: transient → raised so the retry layer can decide (see `LLMClient`'s
  retry policy applies equally to embedding calls).

---

## 4. `VectorStore` (Repository pattern, session-scoped)

```python
class VectorStore(ABC):
    @abstractmethod
    async def add(self, session_id: str, chunks: list[Chunk], embeddings: list[list[float]]) -> None: ...

    @abstractmethod
    async def search(self, session_id: str, query_embedding: list[float], k: int) -> list[tuple[Chunk, float]]: ...

    @abstractmethod
    async def drop_session(self, session_id: str) -> None: ...
```

**Contract**:

- `add` and `search` MUST be scoped to `session_id` — a query in session A MUST NOT
  return chunks from session B (FR-018).
- `search` returns `k` (chunk, score) tuples ordered by descending score; fewer than
  `k` is acceptable for small corpora.
- `drop_session` is idempotent and used by `/session/end` (FR-019/FR-020).
- Implementation: `ChromaVectorStore` with one Chroma collection per session.

---

## 5. `LLMClient` (Strategy pattern)

```python
from typing import AsyncIterator

@dataclass(frozen=True)
class ChatMessage:
    role: str              # "system" | "user" | "assistant"
    content: str

class LLMClient(ABC):
    @property
    @abstractmethod
    def model_name(self) -> str: ...

    @abstractmethod
    async def stream_chat(self, messages: list[ChatMessage]) -> AsyncIterator[str]: ...
```

**Contract**:

- `stream_chat` yields token-string deltas as they arrive from the provider; it
  MUST NOT buffer the full response.
- Implementations apply the retry policy from `src/llm/retry.py`:
  ≤ 2 retries, exponential backoff, 5 s total budget, transient errors only
  (FR-021).
- Implementations: `AnthropicLLMClient` (Messages API streaming),
  `OpenAILLMClient` (Chat Completions streaming).

---

## 6. `ConversationStore` (Repository pattern)

```python
class ConversationStore(ABC):
    @abstractmethod
    async def append(self, session_id: str, turn: ConversationTurn) -> None: ...

    @abstractmethod
    async def get(self, session_id: str) -> list[ConversationTurn]: ...

    @abstractmethod
    async def drop_session(self, session_id: str) -> None: ...
```

**Contract**:

- `get` returns turns in insertion order.
- `append` is atomic per session.
- `drop_session` mirrors `VectorStore.drop_session` for `/session/end`.
- v1 implementation: `InMemoryConversationStore` (a `dict[str, list[ConversationTurn]]`
  guarded by an `asyncio.Lock` per session).

---

## 7. Service Facades

```python
class IngestionService:
    """Facade: parse -> chunk -> embed -> store. Returns a Document handle."""
    async def ingest(self, *, session_id: str, file_path: str, filename: str, mime_type: str) -> Document: ...

class QAService:
    """Facade: retrieve -> build prompt -> stream LLM -> persist turn."""
    async def answer(self, *, session_id: str, question: str) -> AsyncIterator[QAEvent]: ...

@dataclass(frozen=True)
class QAEvent:
    kind: Literal["token", "citations", "done", "error"]
    payload: dict          # shape depends on `kind`; mirrors SSE frames
```

**Contract**:

- `QAService.answer` yields a `citations` event exactly once, BEFORE `done`.
- `QAService.answer` yields ≥ 1 `token` event in the happy path (so the SSE stream
  is verifiable as incremental).
- Both facades hide vector-store / provider internals from API routes. Routes import
  facades, never lower layers.

---

## Factory contract

```python
def make_llm_client(cfg: ProviderConfiguration) -> LLMClient: ...
def make_embedding_provider(cfg: ProviderConfiguration) -> EmbeddingProvider: ...
def make_parser_for(filename: str) -> DocumentParser: ...
```

Factories MUST resolve from configuration only; service code MUST NOT branch on
provider names. Adding a new provider = new class + factory branch + test, with
zero edits in `services/`.
