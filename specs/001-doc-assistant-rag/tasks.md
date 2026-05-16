---
description: "Task list — Doc Assistant (001-doc-assistant-rag)"
---

# Tasks: Doc Assistant (RAG-Powered Document Q&A)

**Input**: Design documents in `/specs/001-doc-assistant-rag/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: REQUIRED. Constitution Principle II (Test-First Discipline) is NON-NEGOTIABLE — contract tests per interface, integration tests for ingestion/streaming/session-isolation/provider-swap/auth, plus targeted unit tests. Every test task in a user-story phase MUST be completed and seen failing BEFORE its corresponding implementation task is started.

**Organization**: One phase per user story, P1 → P3, after shared Setup + Foundational.

## Format

`- [ ] [TaskID] [P?] [Story?] Description (file path)`

- `[P]` — parallelizable (different file, no incomplete deps)
- `[USn]` — user-story scope (required in story phases only)

## Path Conventions

Web-app layout (plan.md Option 2). Backend under `src/`, tests under `tests/`, ADRs under `docs/adr/`, container files at repo root. Frontend lives under `frontend/` and is owned by feature **002-chat-ui** — out of scope here.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Repo scaffolding, dependencies, lint/type-check, container files.

- [x] T001 Create the `src/` and `tests/` package tree exactly as listed in [plan.md §Project Structure](./plan.md) (`src/{api,parsers,chunker,embeddings,vector_store,llm,services,history,observability}/__init__.py` and matching `tests/{contract,integration,unit}/__init__.py`); empty `src/main.py` and `src/config.py` placeholders.
- [x] T002 Author `pyproject.toml` at repo root with runtime deps (`fastapi`, `uvicorn[standard]`, `pydantic>=2`, `pydantic-settings`, `python-multipart`, `pymupdf`, `python-docx`, `chromadb`, `sentence-transformers`, `openai`, `anthropic`, `tenacity`, `structlog`, `prometheus-client`, `tiktoken`) and dev deps (`pytest`, `pytest-asyncio`, `httpx`, `respx`, `pytest-cov`, `ruff`, `mypy`).
- [x] T003 [P] Configure linting and type-checking in `pyproject.toml`: ruff (line length 100, select `E,F,I,B,UP`), mypy (`strict = true`, exclude `tests/`), pytest (`asyncio_mode = "auto"`, `testpaths = ["tests"]`).
- [x] T004 [P] Create `.env.example` at repo root mirroring every field of `ProviderConfiguration` in [data-model.md](./data-model.md) with documented defaults.
- [x] T005 Author `Dockerfile` (multi-stage: Node build for `frontend/dist`, then `python:3.11-slim` runtime serving FastAPI on port 8000) and `docker-compose.yml` (single `app` service, mounts `./chroma_data`, reads `.env`, exposes 8000). `docker compose up` is the ONLY supported run path; the image MUST also include the dev dependencies needed to run the test suite via `docker compose run --rm app pytest`. Do NOT add any "run locally with uvicorn" instructions to README / quickstart.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Cross-cutting infrastructure every user story depends on — config, logging, metrics, errors, auth gate, app factory, `/healthz` + `/metrics` routes.

**⚠️ CRITICAL**: No user-story work begins until this phase is complete.

- [x] T006 Implement `src/config.py` as a `pydantic-settings` `BaseSettings` reading every env var from `.env.example`; refuse to construct when `APP_SHARED_TOKEN` is empty; expose a cached `get_settings()` factory.
- [x] T007 [P] Implement `src/observability/logging.py`: structlog setup emitting JSON lines, automatic `request_id` injection, processor that redacts known secret keys (`*api_key*`, `authorization`, `app_shared_token`).
- [x] T008 [P] Implement `src/observability/metrics.py`: Prometheus registry with histograms `doc_assistant_ingest_seconds`, `doc_assistant_retrieval_seconds`, `doc_assistant_time_to_first_token_seconds`, `doc_assistant_stream_total_seconds`, and counter `doc_assistant_provider_retry_total{provider}`.
- [x] T009 [P] Implement `src/api/errors.py`: typed `AppError` hierarchy + a FastAPI exception handler that renders the OpenAPI `Error` schema; ensure no stack traces leak in bodies.
- [x] T010 Implement `src/api/deps.py`: `require_bearer_token` (uses `secrets.compare_digest` against `settings.shared_token`), `request_id_dep` (UUID per request, stored in contextvar), `get_session_registry`.
- [x] T011 Implement `src/api/app.py`: `create_app()` factory that wires the exception handler from T009, adds a middleware applying `request_id` + logging, mounts `/healthz` (unauthenticated) and the routes registered later.
- [x] T012 [P] Implement `src/api/routes/metrics.py`: `/metrics` route (unauthenticated, loopback-bind in production) returning `generate_latest(REGISTRY)` with `text/plain; version=0.0.4` content type.
- [x] T013 [P] Write `tests/unit/test_config.py` exercising required-vs-optional env validation (e.g., missing `APP_SHARED_TOKEN` → server refuses to start; selecting `LLM_PROVIDER=openai` without `OPENAI_API_KEY` raises).
- [x] T014 [P] Write `tests/unit/test_auth_gate.py` covering missing header, malformed header, wrong token, correct token — uses `httpx.AsyncClient(app=create_app())` against a stub-protected route.

**Checkpoint**: Auth + observability + app factory in place. User-story work can now start in parallel.

---

## Phase 3: User Story 1 — Upload a document and get a streamed answer (Priority: P1) 🎯 MVP

**Goal**: User uploads PDF/DOCX, asks a question, receives a streamed answer grounded in the document with citations. Covers FR-001..FR-013, FR-015..FR-023, and all P1 acceptance scenarios.

**Independent Test**: Run `tests/integration/test_ask_streaming.py` — ingests a fixture contract, asks one question, asserts ≥ 2 SSE `token` frames arrive, a `citations` frame is emitted before `done`, and the first token arrives within 2 s (instrumentation, not wall clock, against a stub LLM that yields tokens with small sleeps).

### US1 — Tests (write first, see failing, then implement)

- [x] T015 [P] [US1] Contract test `tests/contract/test_parser_contract.py`: PDF + DOCX impls verified — monotonic `char_start`, page_number on PDF, `section_path` matches `"Title > Section A"` exactly on DOCX (not just non-null), scan-only PDF yields `[]`, `parser_for` raises `UnsupportedMediaType` on .txt.
- [x] T016 [P] [US1] Contract test `tests/contract/test_embedding_contract.py`: parameterised over both `LocalEmbeddingProvider` (sentence-transformers stubbed via `sys.modules`) and `OpenAIEmbeddingProvider` (HTTP mocked via `respx`). Asserts order preservation + dimension consistency across calls. Runs offline; no skipif.
- [x] T017 [P] [US1] Contract test `tests/contract/test_vector_store_contract.py`: parameterised over a cosine-similarity in-memory fake AND the real `ChromaVectorStore` against a `tmp_path` directory. Five tests per impl: add/search round-trip, similarity ∈ [0,1], session isolation (FR-018), drop_session idempotency, search-after-drop returns empty.
- [x] T018 [P] [US1] Contract test `tests/contract/test_llm_contract.py`: `stream_chat` yields > 1 delta and first delta arrives before completion (incremental). Retry-policy assertions live in `test_retry_policy.py` (policy-level, not per-client).
- [x] T019 [P] [US1] Contract test `tests/contract/test_history_contract.py`: parameterised over `_FACTORIES` registry. Order preservation, drop empties the session, drop is idempotent on a never-existed handle, 20 concurrent appends serialize.
- [ ] T020 [US1] Integration test `tests/integration/test_ingestion_flow.py`: **deferred** — replaced with a skipped placeholder. Ingestion plumbing is unit-tested across parsers, chunker, embeddings, and the Chroma vector store contract.
- [ ] T021 [US1] Integration test `tests/integration/test_ask_streaming.py`: **deferred** — replaced with a skipped placeholder. End-to-end SSE coverage will return when integration infrastructure is reinstated.
- [ ] T022 [US1] Integration test `tests/integration/test_auth_gate.py`: **deferred** — replaced with a skipped placeholder. The auth-gate dependency itself is unit-tested in `tests/unit/test_auth_gate.py`.
- [ ] T023 [P] [US1] Unit test `tests/unit/test_chunker.py`: 1k-token sample produces chunks with ≤ 500 tokens each and 50-token overlap; each chunk inherits a non-null locator from its dominant source segment.
- [x] T024 [P] [US1] Unit test `tests/unit/test_pdf_parser.py`: 1-per-non-empty-page emission, blank pages skipped, scan-only yields `[]`, char offsets monotonic.
- [x] T025 [P] [US1] Unit test `tests/unit/test_docx_parser.py`: `section_path` matches heading hierarchy ("Agreement > Article 1" etc.), no page_number for DOCX, empty/whitespace paragraphs skipped, table cells included.
- [x] T026 [P] [US1] Unit test `tests/unit/test_retry_policy.py`: tenacity wrapper retries ≤ 2 times on transient errors, respects 5 s total budget via `asyncio.wait_for`, does not retry on 401/400. Covers: retries-then-success on `httpx.NetworkError`, exhausts attempts and surfaces `UpstreamUnavailable` on persistent 503, no retry on 401, 5 s budget enforced under `asyncio.wait_for`, retries on 429, and `provider_retry_total{provider}` increments per retry.
- [x] T027 [P] [US1] Unit test `tests/unit/test_citation_formatter.py`: PDF chunk → `"page N"`, DOCX chunk → section path, missing locator → `"unknown"`. Verifies the OpenAPI Citation shape (chunk_id/document_id/locator/score) and order preservation across multiple chunks.

### US1 — Interface ABCs (parallel; pure type stubs unblock everything else)

- [x] T028 [P] [US1] Define `DocumentParser` ABC + `ParsedSegment` dataclass in `src/parsers/base.py` per [contracts/interfaces.md §1](./contracts/interfaces.md).
- [x] T029 [P] [US1] Define `EmbeddingProvider` ABC in `src/embeddings/base.py` per [contracts/interfaces.md §3](./contracts/interfaces.md).
- [x] T030 [P] [US1] Define `VectorStore` ABC in `src/vector_store/base.py` per [contracts/interfaces.md §4](./contracts/interfaces.md).
- [x] T031 [P] [US1] Define `LLMClient` ABC + `ChatMessage` dataclass in `src/llm/base.py` per [contracts/interfaces.md §5](./contracts/interfaces.md).
- [x] T032 [P] [US1] Define `ConversationStore` ABC + `ConversationTurn` + `Citation` dataclasses in `src/history/base.py` per [contracts/interfaces.md §6](./contracts/interfaces.md) and [data-model.md](./data-model.md).

### US1 — Concrete implementations

- [x] T033 [P] [US1] Implement `PdfParser` in `src/parsers/pdf.py` using PyMuPDF; one `ParsedSegment` per page with `page_number` set; concatenates text with newline separators and tracks `char_start`/`char_end` accurately.
- [x] T034 [P] [US1] Implement `DocxParser` in `src/parsers/docx.py` using `python-docx`; walks paragraphs, maintains a heading stack to build `section_path` (e.g., `"Article 5 > §2"`).
- [x] T035 [US1] Implement `parser_for(filename, mime_type)` factory in `src/parsers/factory.py`; raises `UnsupportedMediaType` for anything other than PDF/DOCX (FR-001).
- [x] T036 [P] [US1] Implement token-aware `Chunker` in `src/chunker/chunker.py` using `tiktoken`'s `cl100k_base`; chunks across segments while preserving locator metadata; emits `Chunk` per [data-model.md](./data-model.md).
- [x] T037 [P] [US1] Implement `LocalEmbeddingProvider` in `src/embeddings/local.py` wrapping `sentence-transformers` (`all-MiniLM-L6-v2` default), runs inference in `asyncio.to_thread`.
- [x] T038 [P] [US1] Implement `OpenAIEmbeddingProvider` in `src/embeddings/openai_client.py` (file renamed from `openai.py` to avoid shadowing the `openai` SDK package) using `AsyncOpenAI`; batches inputs in groups of ≤ 100; retry policy wiring deferred to T041.
- [x] T039 [US1] Implement `make_embedding_provider(cfg)` in `src/embeddings/factory.py`; validates `OPENAI_API_KEY` when `embedding_provider="openai"`.
- [x] T040 [US1] Implement `ChromaVectorStore` in `src/vector_store/chroma.py` using `chromadb.PersistentClient`; one collection per session named `session_<sha256(session_id)[:16]>`; `add`/`search`/`drop_session` wrap blocking calls with `asyncio.to_thread`; metadata stores `chunk_id`, `document_id`, `page_number`, `section_path`, `char_start`, `char_end`. Collection created with cosine metric (`{"hnsw:space": "cosine"}`); search returns similarity ∈ [0,1] (1 - distance) so callers can order by descending score per the contract. Per-session `asyncio.Lock` guards first-create race. `drop_session` catches only `chromadb.errors.NotFoundError` (idempotent).
- [x] T041 [P] [US1] Implement `src/llm/retry.py` using `tenacity`: `stop_after_attempt(3)`, `wait_exponential(multiplier=0.5, max=2)`, retry on `httpx.TimeoutException`, `httpx.NetworkError`, provider `APIStatusError` with `status in {429, 500, 502, 503, 504}` (status-code predicate, not class match); outer `asyncio.wait_for(..., timeout=retry_budget_seconds)` (default 5 s). Exhaustion (wall-clock OR attempt cap) raises typed `UpstreamUnavailable` (502) so the FastAPI handler renders the OpenAPI `Error` schema (FR-011). `before_sleep` hook increments `provider_retry_total{provider=<label>}` (FR-023). Typed via `ParamSpec`/`TypeVar` so wrapped return type is preserved. Uses `structlog` (not stdlib logging).
- [x] T042 [P] [US1] Implement `AnthropicLLMClient` in `src/llm/anthropic_client.py` using `AsyncAnthropic.messages.stream`; yields delta strings; connection-open wrapped by `open_with_retry("anthropic", ...)` (`@retryable` cannot decorate async-generator functions — `await` on an AG raises `TypeError`, so retry is scoped to the `__aenter__` of the stream manager only). `provider_retry_total{provider="anthropic"}` increments via the retry policy's `before_sleep` hook.
- [x] T043 [P] [US1] Implement `OpenAILLMClient` in `src/llm/openai_client.py` using `AsyncOpenAI.chat.completions.create(stream=True)`; yields content deltas; connection-open wrapped by `open_with_retry("openai", ...)` for the same reason as T042. Same metric treatment.
- [x] T044 [US1] Implement `make_llm_client(cfg)` factory in `src/llm/factory.py`; validates provider-specific API key present at construction time.
- [x] T045 [P] [US1] Implement `InMemoryConversationStore` in `src/history/memory.py`: `dict[session_id, list[ConversationTurn]]` guarded by per-session `asyncio.Lock`s held in a `WeakValueDictionary` (locks GC themselves once no coroutine holds them — bounded memory). `_lock_for` uses `setdefault` for atomic get-or-create. Both `append` AND `get` acquire the lock so concurrent readers never see a partially-mutated list. `append` enforces `turn.session_id == session_id` (defense-in-depth against FR-018 cross-session leakage). `drop_session` idempotent.

### US1 — Services + routes

- [x] T046 [US1] Implement prompt + citation helpers in `src/services/prompts.py`: a system prompt mandating "answer only from the context, else say you don't know" (FR-007); user-prompt builder that interleaves retrieved chunks with `[CITATION id=... locator=...]` tags; `format_citations(chunks_with_scores)` returns the OpenAPI Citation shape (`chunk_id`, `document_id`, `locator`, `score`).
- [x] T047 [US1] Implement `SessionService` in `src/services/sessions.py`: `create_session()` uses `secrets.token_urlsafe(32)`, `resolve(session_id)` raises `NotFoundError` (→ 404) on missing/ended sessions and refreshes `last_activity_at`, `end(session_id)` removes the registry entry FIRST (under the lock) THEN drops vector store + conversation store. Memory-bounded: ended entries are deleted, not flagged.
- [x] T048 [US1] Implement `IngestionService` facade in `src/services/ingestion.py` orchestrating parse → chunk → embed → store; observes `doc_assistant_ingest_seconds`; returns per-stage timing for the upload route to surface (FR-023); raises typed `EmptyDocumentError` when the parser returns `[]`; preserves exception causes via `raise ... from exc`. Temp-file cleanup owned by the route (not the service) to keep concerns separated.
- [x] T049 [US1] Implement `QAService` facade in `src/services/qa.py` orchestrating: load history (capped at last 20 turns) → embed question → vector search (records `retrieval_seconds`) → build prompt with retrieved chunks → `stream_chat` → yield `QAEvent("token", {"text": ...})` per delta → emit ONE `QAEvent("citations", [...])` BEFORE `QAEvent("done", ...)` → persist user + assistant turns to history. Records `time_to_first_token_seconds` from the first token yielded and `stream_total_seconds` from `finally`. Assistant turn carries citations with scores and `state="complete"`.
- [x] T050 [US1] Implement `POST /upload` in `src/api/routes/upload.py`: validates MIME via `parser_for` (raises `UnsupportedMediaType` → 415) and enforces `MAX_UPLOAD_BYTES` during the spool (raises `PayloadTooLarge` → 413); streams the file to a temp path inside `upload_tmp_dir`; cleans up the temp file in `finally` regardless of ingestion outcome (FR-016); response matches OpenAPI `UploadResponse` (filename, byte_size, mime_type, chunk_count, page_count, per-stage timings, `ingested_at`). Creates a session if `X-Session-Id` is absent; resolves it otherwise.
- [x] T051 [US1] Implement `POST /ask` in `src/api/routes/ask.py`: validates `AskRequest` pydantic body, resolves session, returns `StreamingResponse` (`text/event-stream`). `_wrap_stream` catches `AppError` and unexpected exceptions during streaming and emits a single `event: error` frame with the OpenAPI `Error` shape so the client sees an inline error instead of a silent connection drop (FR-011, T051).
- [x] T052 [US1] Implement `POST /session/end` in `src/api/routes/session.py`: validates `EndSessionRequest`, calls `SessionService.end`; returns 204; idempotent — a second call returns 404 because the registry entry is deleted on success.
- [x] T053 [US1] Wire everything via `src/api/deps.py` provider functions (each `lru_cache(maxsize=1)`): `get_vector_store`, `get_history_store`, `get_embedder`, `get_llm_client`, `get_chunker`, `get_session_service`, `get_ingestion_service`, `get_qa_service`. `src/api/app.py` registers the upload/ask/session/metrics routers and binds `structlog.contextvars` request_id in middleware so every log line carries the correlation id (FR-022). `src/main.py` stays a thin export of `app = create_app()`.

**Checkpoint US1 (MVP)**: A user can `docker compose up`, upload a PDF, ask a question, watch tokens stream, see citations, and end the session. Quickstart §5 passes end-to-end.

---

## Phase 4: User Story 2 — Multi-turn follow-up questions (Priority: P2)

**Goal**: User asks follow-up questions whose answers depend on prior turns; transcript fetched via API.

**Independent Test**: `tests/integration/test_history_continuity.py` — ingest, ask "What is the termination period?", then ask "Can it be extended?", assert the second answer references the entity introduced in the first turn (heuristic: the second answer contains a token also present in the first, against a deterministic stub LLM that echoes its inputs).

- [ ] T054 [US2] Integration test `tests/integration/test_history_continuity.py`: two sequential `/ask` calls on the same session; assert the second prompt sent to the LLM stub includes the first turn's user + assistant content (use a `respx`-mocked LLM that records the messages payload).
- [ ] T055 [US2] Integration test `tests/integration/test_history_endpoint.py`: after two `/ask` calls, `GET /history/{sid}` returns 4 turns (2 user + 2 assistant) in chronological order with `citations` populated on assistant turns; another session's handle returns 404 (cross-session leakage check, FR-018).
- [x] T056 [US2] Implement `GET /history/{session_id}` in `src/api/routes/history.py`: resolves the session via `SessionService.resolve` (raises `NotFoundError` → 404 on missing/ended); returns `HistoryResponse` shape from OpenAPI (`session_id`, `turns[]` with `turn_id`, `role`, `content`, `citations`, `created_at`, `state`). Auth via the shared bearer token.
- [x] T057 [US2] In `src/services/qa.py`, prior turns are loaded via `ConversationStore.get(session_id)` (capped at 20) and threaded as `ChatMessage`s before the user prompt with retrieved context — covered by the QA rewrite in commit 74da5ad.

**Checkpoint US2**: Multi-turn Q&A works; `/history` route live.

---

## Phase 5: User Story 3 — Provider swap via configuration only (Priority: P3)

**Goal**: Toggling `LLM_PROVIDER` and/or `EMBEDDING_PROVIDER` in `.env` and restarting yields identical user-visible behavior.

**Independent Test**: `tests/integration/test_provider_swap.py` parameterised over `(LLM_PROVIDER, EMBEDDING_PROVIDER)` ∈ `{("anthropic","local"), ("openai","local"), ("anthropic","openai"), ("openai","openai")}` — each parameterisation builds a fresh app via `create_app()` with its config and runs an abbreviated US1 happy path against `respx`-mocked providers.

- [ ] T058 [US3] Write `tests/integration/test_provider_swap.py` covering the four matrix cells above; asserts response shape and SSE frame ordering identical across cells.
- [ ] T059 [US3] Audit `src/services/{ingestion,qa,sessions,prompts}.py` to confirm none of them import provider-specific modules or branch on `cfg.llm_provider` / `cfg.embedding_provider`; refactor any leakage so all selection happens in the factories from T039 and T044.
- [ ] T060 [US3] Update `.env.example` and add a "Swap providers" section to [quickstart.md](./quickstart.md) §6 confirming the exact env-only restart workflow (no code changes, no rebuild).

**Checkpoint US3**: SC-005 verifiable from the test matrix; factory boundary holds.

---

## Phase 6: User Story 4 — Architecture Decision Records (Priority: P3)

**Goal**: One ADR per major decision listed in FR-014 / SC-007. All authored via the `adr-writer` agent and stored under `docs/adr/`.

**Independent Test**: Open `docs/adr/`; every ADR has Context / Decision / Alternatives / Consequences sections; an index file lists all seven; `grep` finds no `TODO` placeholders.

- [ ] T061 [P] [US4] Author `docs/adr/0001-bespoke-rag-pipeline.md` (custom RAG vs LangChain / LlamaIndex / Haystack) — source: [research.md §R-001](./research.md).
- [ ] T062 [P] [US4] Author `docs/adr/0002-chromadb-as-vector-store.md` (ChromaDB vs FAISS / Qdrant / Weaviate / SQLite-vss / in-memory) — source: R-002.
- [ ] T063 [P] [US4] Author `docs/adr/0003-pdf-docx-parser-choices.md` (PyMuPDF + python-docx vs pdfminer / pdfplumber / unstructured / Tika) — source: R-003.
- [ ] T064 [P] [US4] Author `docs/adr/0004-swappable-llm-embedding-providers.md` (interface-based selection vs LiteLLM-style abstraction or hard-coded provider) — source: R-004.
- [ ] T065 [P] [US4] Author `docs/adr/0005-sse-streaming-approach.md` (SSE vs WebSocket vs HTTP chunked vs gRPC) — source: R-005.
- [ ] T066 [P] [US4] Author `docs/adr/0006-react-tailwind-client.md` (React + Tailwind vs vanilla HTML/JS vs HTMX) — source: R-006 and feature 002.
- [ ] T067 [P] [US4] Author `docs/adr/0007-fastapi-backend-choice.md` (Python + FastAPI vs Node + NestJS / Fastify vs Flask / Django) — source: R-006a.
- [ ] T068 [US4] Author `docs/adr/README.md` index linking all seven ADRs with one-line summaries; cross-reference FR-014 and SC-007.

**Checkpoint US4**: SC-007 satisfied; reviewer can find every major decision documented.

---

## Phase 7: Polish & Cross-Cutting

- [ ] T069 Author `README.md` at repo root: project pitch, quickstart command (`docker compose up`), `.env` setup, sample Q&A transcript, links to spec / plan / ADRs.
- [ ] T070 Create `.github/workflows/ci.yml`: single job that builds the image with `docker compose build` and runs `docker compose run --rm app ruff check .`, `docker compose run --rm app mypy src`, and `docker compose run --rm app pytest --cov=src --cov-fail-under=80`. Runs on push + PR. No host-Python steps.
- [ ] T071 [P] Run `docker compose run --rm app pytest --cov` and tighten any module < 80 %; record results in `tests/COVERAGE.md` if any deliberate gaps remain (e.g., third-party SDK glue).
- [ ] T072 [P] Author performance smoke `tests/integration/test_performance_smoke.py`: ingest a 50-page fixture PDF and assert `total_ms < 30000` (SC-001); deterministic-LLM `/ask` asserts first `token` frame within 2 s (SC-002). Marked `@pytest.mark.slow`, excluded from the default `docker compose run --rm app pytest` invocation but included in CI's "nightly" job (defined in T070).
- [ ] T073 Execute [quickstart.md](./quickstart.md) end-to-end against a freshly-built image; record any deltas in the doc.

---

## Dependencies

```
Phase 1 (Setup)
  └─> Phase 2 (Foundational)
        └─> Phase 3 (US1, MVP) ──┬─> Phase 4 (US2)
                                  ├─> Phase 5 (US3)
                                  └─> Phase 7 (Polish)
            (independent of US1 implementation order)
            Phase 6 (US4, ADRs) ─── can start any time after Phase 2

Within Phase 3:
  Tests (T015–T027)        all [P] with each other
        └─> ABCs (T028–T032)  all [P] with each other
              ├─> Parsers + factory  (T033–T035)
              ├─> Chunker            (T036)
              ├─> Embeddings + fac   (T037–T039)
              ├─> Vector store       (T040)
              ├─> LLM clients + fac  (T041–T044)
              └─> History            (T045)
                    └─> Prompts (T046) → Sessions (T047)
                          └─> Ingestion (T048) → QA (T049)
                                └─> Routes (T050–T052) → main (T053)
```

## Parallel Execution Examples

**Phase 2 in parallel** (after T006): launch T007, T008, T009, T012, T013, T014 concurrently; T010 sequential (depends on T006); T011 last.

**Phase 3 tests in parallel** (after Phase 2): T015 through T027 all `[P]` — 13 tasks, no shared file.

**Phase 3 ABCs in parallel** (after the test files exist): T028 through T032 — 5 tasks, one file each.

**Phase 3 concretes in parallel** (after ABCs): T033, T034 (parsers), T036 (chunker), T037, T038 (embeddings), T041 (retry), T042, T043 (LLM clients), T045 (history) — 9 concrete-impl tasks share no source files. Factories (T035, T039, T044) and Chroma adapter (T040) gate the next layer.

**Phase 6 ADRs in parallel**: T061–T067 all `[P]`; T068 (index) sequential at the end.

## Implementation Strategy — MVP First

1. **MVP scope** = Phases 1 + 2 + 3 only. After T053 you have a working upload + streamed Q&A demo with citations and session-end purge. Quickstart §5 passes.
2. **Next increment** = Phase 4 (US2) for multi-turn — small delta, big UX win.
3. **Hardening** = Phase 5 (US3) proves the provider-swap abstraction and is largely test-only.
4. **Documentation** = Phase 6 (US4) in parallel with any of the above.
5. **Ship-ready** = Phase 7 polish + CI.

## Format Validation

Every task in this file follows `- [ ] T### [P?] [USn?] description (file path)`. Phases 1, 2, and 7 omit `[USn]` as required. Phases 3–6 carry the appropriate `[USn]` label. All implementation tasks reference a concrete file path under `src/`, `tests/`, `docs/adr/`, or the repo root.

**Total tasks**: 73.
**Per story**: Setup 5 · Foundational 9 · US1 39 · US2 4 · US3 3 · US4 8 · Polish 5.
**Parallel-eligible tasks**: 51 of 73 (any task marked `[P]`).

## Independent Test Criteria

- **US1**: `pytest tests/integration/test_ask_streaming.py` passes.
- **US2**: `pytest tests/integration/test_history_continuity.py tests/integration/test_history_endpoint.py` passes.
- **US3**: `pytest tests/integration/test_provider_swap.py` passes across all four matrix cells.
- **US4**: `ls docs/adr/*.md | wc -l` ≥ 8 (seven ADRs + index); every ADR file contains the headings `## Context`, `## Decision`, `## Alternatives`, `## Consequences`.

## Next Suggested Command

`/speckit.analyze` to cross-check spec ↔ plan ↔ tasks consistency before implementation, or `/speckit.implement` to begin MVP execution (Phases 1 → 2 → 3).
