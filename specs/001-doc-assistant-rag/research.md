# Research: Doc Assistant (RAG-Powered Document Q&A)

**Phase**: 0
**Date**: 2026-05-16
**Branch**: `001-doc-assistant-rag`

No `NEEDS CLARIFICATION` markers remained in spec or plan after `/speckit.clarify`.
This document records the best-practice research that informs each technology choice
and pre-empts the corresponding ADR in `docs/adr/`.

---

## R-001 Bespoke RAG pipeline vs. orchestration framework

- **Decision**: Build a bespoke retrieval pipeline with explicit interfaces; do NOT
  introduce LangChain or LlamaIndex.
- **Rationale**:
  - Project brief and constitution Principle I explicitly forbid them — the project
    exists to demonstrate clean OOP + design patterns.
  - Framework abstractions hide the layering this codebase is meant to showcase
    (Strategy for parsers, Factory for parser/provider selection, Repository for vector
    store + history, Facade for ingestion/QA services).
  - Avoids upstream churn (LangChain releases break APIs frequently).
- **Alternatives considered**:
  - LangChain — fastest path to a demo, but heavy abstractions, frequent breaking
    changes, large transitive dependency footprint.
  - LlamaIndex — narrower than LangChain, still adds an abstraction layer over our
    interfaces.
  - Haystack — closer to our layering but adds dependencies we do not need.
- **ADR**: `docs/adr/0001-bespoke-rag-pipeline.md`.

## R-002 Vector store

- **Decision**: ChromaDB, file-backed (`PersistentClient`), one collection per session.
- **Rationale**:
  - Zero external services (KICKOFF FR-013, SC-008 require single `docker compose up`).
  - Mature Python client, decent recall, supports metadata filtering (used for chunk
    page/section locators required by FR-007a).
  - Per-session collection cleanly enforces session isolation (FR-018).
  - Deletion is O(collection-size); supports explicit-end purge (FR-019).
- **Alternatives considered**:
  - FAISS — fast, in-process, but no metadata, no persistence semantics, manual index
    management.
  - Qdrant / Weaviate — heavier; require a separate service or embedded mode that
    contradicts the "no separate DB" goal.
  - SQLite + `sqlite-vss` extension — interesting but adds extension binary management
    and is less battle-tested for embeddings.
  - In-memory dict + cosine — fine for ≤ 1k chunks but violates the SC for scaling to
    larger corpora and breaks the Repository pattern abstraction.
- **ADR**: `docs/adr/0002-chromadb-as-vector-store.md`.

## R-003 PDF and DOCX parsing

- **Decision**: PyMuPDF (`fitz`) for PDFs, `python-docx` for DOCX.
- **Rationale**:
  - PyMuPDF: fast, robust, reliable text extraction with page coordinates → satisfies
    FR-007a (page-level locators) cheaply. C-backed; well under the 30 s ingest budget
    for 50-page PDFs.
  - python-docx: standard, pure-Python, simple. Walks paragraphs + headings, which
    gives us section-level locators for DOCX citations.
- **Alternatives considered**:
  - `pdfminer.six` — pure-Python, slower, fewer locator helpers.
  - `pdfplumber` — built on pdfminer; nicer API but still slower; useful for table
    extraction (not needed v1).
  - `unstructured` / `docling` — more capable but heavyweight and contradict the
    "minimal dependency footprint" rule from constitution Additional Constraints.
  - Tika — JVM dependency; rejected.
- **ADR**: `docs/adr/0003-pdf-docx-parser-choices.md`.

## R-004 Swappable LLM and embedding providers

- **Decision**: Two interfaces — `LLMClient.stream_chat()` and `EmbeddingProvider.embed()`.
  Concrete: `anthropic` SDK + `openai` SDK for LLM; `sentence-transformers`
  (`all-MiniLM-L6-v2` default) + `openai` for embeddings. Selection via env (`LLM_PROVIDER`,
  `EMBEDDING_PROVIDER`) resolved by a factory at startup.
- **Rationale**:
  - Spec FR-010 and constitution Principle V require provider swap with no code change.
  - Two providers per role is the smallest set that proves the abstraction holds.
  - Anthropic Claude is the brief's "default reasoning" choice; OpenAI is the obvious
    alternative.
  - Local embeddings remove an API dependency for offline demos; OpenAI embeddings give
    a quality comparison.
- **Alternatives considered**:
  - Provider-agnostic libraries (LiteLLM) — defeats the point of building the interface.
  - Hard-coding Anthropic only — fails FR-010.
- **ADR**: `docs/adr/0004-swappable-llm-embedding-providers.md`.

## R-005 Streaming transport

- **Decision**: Server-Sent Events (SSE) over HTTP, served by FastAPI's
  `StreamingResponse` with `text/event-stream`. Event types: `token`, `citations`,
  `done`, `error`.
- **Rationale**:
  - SSE is unidirectional (server → client), perfect for token streams, and supported
    natively by browsers via `EventSource` without extra libraries — aligns with the
    React client in feature 002.
  - Avoids WebSocket framing overhead and reconnection state when we don't need
    client→server streaming.
  - Easy to test: a `pytest` integration test can read the stream chunk-by-chunk and
    assert > 1 event arrived before the response closed.
- **Alternatives considered**:
  - WebSockets — bidirectional, but heavier; we only stream one direction.
  - HTTP chunked transfer with custom delimiter — works but reinvents SSE.
  - gRPC streaming — overkill for a single-machine demo; browser support needs a proxy.
- **ADR**: `docs/adr/0005-sse-streaming-approach.md`.

## R-006a Backend language + web framework

- **Decision**: Python 3.11+ with FastAPI for the backend.
- **Rationale**:
  - KICKOFF.md and constitution Additional Constraints lock this stack.
  - The RAG ecosystem is Python-native: `sentence-transformers`, `chromadb`,
    `PyMuPDF`, `tiktoken`, `anthropic`, `openai` all ship mature Python clients with
    parity to or ahead of their JS counterparts.
  - FastAPI gives async, Pydantic validation, OpenAPI generation, and
    `StreamingResponse` for SSE in one package — minimal glue.
  - Constitution Principle I requires interface-driven layering; FastAPI's
    `Depends` injection composes with our Factory/Repository/Facade patterns
    without dragging in a heavy DI container.
- **Alternatives considered**:
  - **NestJS (Node + TypeScript)** — unifies language with the React client and has
    rich decorator-based DI, but the embedding/PDF ecosystem in Node is thinner
    (`@xenova/transformers`, ChromaDB JS client) and would force either a Python
    sidecar for ML or accept worse-quality libs. Net: more glue, not less.
  - **Fastify (Node + TypeScript)** — fast and lean, but no built-in DI: we'd
    hand-roll the patterns the constitution requires, again on a thinner ML stack.
  - **Flask / Django** — synchronous defaults; would not meet the p95 first-token
    SLO without significant async retrofitting.
  - **Starlette directly** — FastAPI is Starlette plus validation/DI; no reason
    to drop validation.
- **ADR**: `docs/adr/0007-fastapi-backend-choice.md`.

## R-006 Client tech stack (cross-reference, owned by feature 002)

- **Decision**: React 19 + TypeScript + Vite + Tailwind CSS.
- **Rationale**: User mandate. Documented in feature 002 spec (FR-020, FR-021) and
  this feature's FR-014(f) / SC-007.
- **Alternatives considered**: Vanilla HTML+JS (KICKOFF suggestion), HTMX (server-driven
  alt) — see ADR for tradeoffs (bundle size, build pipeline, accessibility).
- **ADR**: `docs/adr/0006-react-tailwind-client.md`.

## R-007 Async I/O posture

- **Decision**: All request-path I/O is async. Anthropic and OpenAI SDKs have async
  clients (`AsyncAnthropic`, `AsyncOpenAI`); ChromaDB is sync, so calls are wrapped
  with `fastapi.concurrency.run_in_threadpool` or `asyncio.to_thread`.
  sentence-transformers inference runs in a thread (CPU-bound).
- **Rationale**: Constitution Principle IV forbids `requests`-style blocking I/O on
  the request path. Threading the sync libraries keeps the event loop free for SSE
  fan-out.
- **Alternatives considered**: pure sync FastAPI — simpler but caps concurrent streams
  at the worker pool size, fails the p95 first-token budget under modest load.

## R-008 Retry policy (transient provider errors)

- **Decision**: `tenacity` with `stop=stop_after_attempt(3)` (1 initial + 2 retries),
  `wait=wait_exponential(multiplier=0.5, max=2)`, retry only on:
  `httpx.TimeoutException`, `httpx.NetworkError`, `anthropic.APIStatusError`/
  `openai.APIStatusError` where `status_code in {429, 500, 502, 503, 504}`. Wall-clock
  budget enforced with `asyncio.wait_for(..., timeout=5.0)` around each provider call.
- **Rationale**: Matches FR-021 verbatim. tenacity is the canonical Python retry lib;
  composes with `await` cleanly. Wall-clock cap prevents pathological backoff stacks.
- **Alternatives considered**: `backoff` package — fine but less feature-rich than
  tenacity; rolling our own — needless re-invention.

## R-009 Observability — logs + metrics

- **Decision**: `structlog` for JSON-line structured logs (request_id, level, event,
  session_handle_hash, latency_ms); `prometheus_client` exposing `/metrics`:
  `ingest_seconds_histogram`, `retrieval_seconds_histogram`, `time_to_first_token_seconds`,
  `stream_total_seconds`, `provider_retry_total{provider}`.
- **Rationale**: Matches FR-022/FR-023. structlog supports key-value events with no
  secrets leakage when paired with a custom processor that scrubs known secret keys.
  prometheus-client is the de-facto standard Python metrics lib and gives us a pull
  endpoint without an external collector.
- **Alternatives considered**: OpenTelemetry full stack — overkill per Q5
  clarification; plain logging module — fails structured-logs requirement.

## R-010 Authentication — shared bearer token

- **Decision**: FastAPI dependency `require_token` validates the `Authorization:
  Bearer <token>` header against `APP_SHARED_TOKEN` from env using
  `secrets.compare_digest`. Applied to every route except `/healthz`. Missing/invalid
  token → 401 with a generic body (no leak).
- **Rationale**: Matches FR-017. Constant-time compare prevents timing oracles.
- **Alternatives considered**: HTTP Basic — fine but `Authorization: Bearer` is the
  modern convention and easier for `EventSource` to set via a fetch-EventSource shim
  in the client.

## R-011 Session handles and isolation

- **Decision**: `secrets.token_urlsafe(32)` for session handles. Server keeps an
  in-memory dict `sessions: dict[handle, SessionState]`. Each `SessionState` carries
  the session's ChromaDB collection name (`session_<short-hash>`), conversation
  history, and a `last_activity` timestamp (for diagnostics only — no TTL purge per
  Q2 clarification).
- **Rationale**: Matches FR-018 (unguessable, isolated). 32-byte url-safe ≈ 43 chars
  of base64url — well above brute-force concern.
- **Alternatives considered**: UUID4 — guessable surface is the same in practice but
  `secrets.token_urlsafe` is the documented "use this for security tokens" path.

## R-012 Chunking strategy

- **Decision**: Token-based chunking with `tiktoken`'s `cl100k_base` encoder (or
  `transformers`' tokenizer fallback). `CHUNK_SIZE=500`, `CHUNK_OVERLAP=50` defaults
  (KICKOFF). Chunk metadata: `chunk_id` (deterministic), `doc_id`, `page_number` (PDF)
  or `section_path` (DOCX), `char_start`, `char_end`.
- **Rationale**: Token chunking (not chars) keeps embedding-model context windows
  honest. 500/50 is a well-trodden default for QA over legal text. Locators in
  metadata satisfy FR-007a citation requirement.
- **Alternatives considered**: Sentence/paragraph chunking — uneven sizes hurt
  embedding batches; recursive character splitter — works but token-aware is more
  faithful to model limits.

## R-013 Testing strategy

- **Decision**:
  - Contract tests parameterised over interface implementations (e.g., the embedding
    contract test runs against both `LocalEmbeddingProvider` and a stub-backed
    `OpenAIEmbeddingProvider`).
  - Integration test for `/ask` reads the SSE stream via `httpx.AsyncClient.stream()`
    and asserts ≥ 2 chunks arrive before stream end, plus a `citations` event with at
    least one chunk id.
  - LLM/embedding HTTP calls mocked with `respx` to keep tests offline and
    deterministic.
  - Coverage gate: ≥ 80% lines on `src/` excluding `__init__.py` and `main.py`.
- **Rationale**: Constitution Principle II requires per-interface contract tests + an
  incremental-stream assertion. `respx` is the canonical httpx mocker and works with
  both Anthropic and OpenAI SDKs (both use httpx under the hood).
- **Alternatives considered**: live API tests — flaky, costly, leak keys; recording
  with VCR — useful but harder to update.

## R-014 Containerization

- **Decision**: Single `python:3.11-slim` image for backend; multi-stage build for
  frontend (Node build → static assets served by FastAPI under `/`). `docker-compose.yml`
  with one service exposes 8000.
- **Rationale**: Matches FR-013 ("single bring-up command") and SC-008 (5-minute
  bring-up). Avoiding a second container keeps the demo tight.
- **Alternatives considered**: Separate backend + nginx containers — more "correct"
  but adds setup time and is unnecessary for the demo footprint.

---

All decisions trace back to a specific FR/SC/principle. No open NEEDS CLARIFICATION.
Proceed to Phase 1 (data model + contracts + quickstart).
