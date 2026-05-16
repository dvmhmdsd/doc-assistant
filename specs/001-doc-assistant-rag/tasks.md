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

- [ ] T015 [P] [US1] Contract test `tests/contract/test_parser_contract.py`: any `DocumentParser` returns ordered `ParsedSegment`s with monotonic `char_start`, carries either `page_number` (PDF) or `section_path` (DOCX), and returns `[]` on a fixture scan-only PDF.
- [ ] T016 [P] [US1] Contract test `tests/contract/test_embedding_contract.py`: any `EmbeddingProvider` returns vectors of `dimensions` floats, preserves input order, and `dimensions` is consistent across calls. Parameterised over `LocalEmbeddingProvider` and an `OpenAIEmbeddingProvider` whose HTTP calls are mocked via `respx`.
- [ ] T017 [P] [US1] Contract test `tests/contract/test_vector_store_contract.py`: `add` then `search` returns the same chunks; `search(session=A)` never returns chunks stored under `session=B` (FR-018); `drop_session` is idempotent.
- [ ] T018 [P] [US1] Contract test `tests/contract/test_llm_contract.py`: `stream_chat` yields multiple deltas (asserts `len(list(stream)) > 1` against a stub provider that simulates per-token chunks); retry policy fires exactly twice on a transient 503 and surfaces after the 5 s budget; non-transient 401 surfaces immediately.
- [ ] T019 [P] [US1] Contract test `tests/contract/test_history_contract.py`: `append` then `get` preserves insertion order; `drop_session` empties the session; concurrent `append`s in the same session are serialized.
- [ ] T020 [US1] Integration test `tests/integration/test_ingestion_flow.py`: upload a fixture 5-page PDF via `httpx.AsyncClient`, assert response shape matches `UploadResponse`, `chunk_count > 0`, on-disk temp dir is empty after the call (FR-016), and a follow-up upload reuses the same session via `X-Session-Id`.
- [ ] T021 [US1] Integration test `tests/integration/test_ask_streaming.py`: ingest fixture, POST `/ask` and read the SSE stream chunk-by-chunk via `httpx.AsyncClient.stream`; assert at least two `event: token` frames arrived (NOT buffered), exactly one `event: citations` frame arrived BEFORE `event: done`, citations payload has ≥ 1 chunk with a non-empty locator (FR-007a).
- [ ] T022 [US1] Integration test `tests/integration/test_auth_gate.py`: missing `Authorization` header on `/upload`, `/ask`, `/history`, `/session/end` → 401; correct `Bearer <token>` → 2xx (uses fixtures from T020).
- [ ] T023 [P] [US1] Unit test `tests/unit/test_chunker.py`: 1k-token sample produces chunks with ≤ 500 tokens each and 50-token overlap; each chunk inherits a non-null locator from its dominant source segment.
- [ ] T024 [P] [US1] Unit test `tests/unit/test_pdf_parser.py`: fixture PDF yields per-page segments with correct `page_number`; scan-only fixture yields `[]`.
- [ ] T025 [P] [US1] Unit test `tests/unit/test_docx_parser.py`: fixture DOCX yields segments tagged with `section_path` reflecting heading hierarchy.
- [ ] T026 [P] [US1] Unit test `tests/unit/test_retry_policy.py`: tenacity wrapper retries ≤ 2 times on transient errors, respects 5 s total budget via `asyncio.wait_for`, does not retry on 401/400.
- [ ] T027 [P] [US1] Unit test `tests/unit/test_citation_formatter.py`: PDF chunk → `"page N"`, DOCX chunk → section path, missing locator → handled gracefully.

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
- [ ] T040 [US1] Implement `ChromaVectorStore` in `src/vector_store/chroma.py` using `chromadb.PersistentClient`; one collection per session named `session_<sha256(session_id)[:16]>`; `add`/`search`/`drop_session` wrap blocking calls with `asyncio.to_thread`; metadata stores `chunk_id`, `document_id`, `page_number`, `section_path`, `char_start`, `char_end`.
- [ ] T041 [P] [US1] Implement `src/llm/retry.py` using `tenacity`: `stop_after_attempt(3)`, `wait_exponential(multiplier=0.5, max=2)`, retry on `httpx.TimeoutException`, `httpx.NetworkError`, provider `APIStatusError` with `status in {429, 500, 502, 503, 504}`; outer `asyncio.wait_for(..., timeout=settings.retry_budget_seconds)` (default 5 s).
- [ ] T042 [P] [US1] Implement `AnthropicLLMClient` in `src/llm/anthropic_client.py` using `AsyncAnthropic.messages.stream`; yields delta strings; wrapped in retry policy from T041; increments `provider_retry_total{provider="anthropic"}` from T008.
- [ ] T043 [P] [US1] Implement `OpenAILLMClient` in `src/llm/openai_client.py` using `AsyncOpenAI.chat.completions.create(stream=True)`; yields content deltas; same retry + metrics treatment.
- [ ] T044 [US1] Implement `make_llm_client(cfg)` factory in `src/llm/factory.py`; validates provider-specific API key present.
- [ ] T045 [P] [US1] Implement `InMemoryConversationStore` in `src/history/memory.py`: `dict[session_id, list[ConversationTurn]]` guarded by per-session `asyncio.Lock`s held in a `WeakValueDictionary`.

### US1 — Services + routes

- [ ] T046 [US1] Implement prompt + citation helpers in `src/services/prompts.py`: a system prompt that mandates "answer only from the context, else say you don't know" (FR-007), a user-prompt builder that interleaves retrieved chunks with their citation tags, and a `format_citations(chunks)` helper used to emit the `event: citations` frame.
- [ ] T047 [US1] Implement `SessionRegistry` + `SessionService` in `src/services/sessions.py`: `create_session()` uses `secrets.token_urlsafe(32)`, `resolve(session_id)` raises 404 on missing/ended sessions, `end(session_id)` calls both `VectorStore.drop_session` and `ConversationStore.drop_session` and marks the entry ended (FR-018, FR-019, FR-020).
- [ ] T048 [US1] Implement `IngestionService` facade in `src/services/ingestion.py` orchestrating parse → chunk → embed → store; records each stage in T008's histogram; cleans the temp upload directory after ingestion (FR-016); raises a typed `EmptyDocumentError` when the parser returns `[]`.
- [ ] T049 [US1] Implement `QAService` facade in `src/services/qa.py` orchestrating: load history → embed question → vector search → build prompt with retrieved chunks → `stream_chat` → yield `QAEvent("token", ...)` per delta → emit ONE `QAEvent("citations", ...)` BEFORE `QAEvent("done", ...)` → persist a `ConversationTurn` to history. Records `time_to_first_token_seconds` from the first token yielded.
- [ ] T050 [US1] Implement `POST /upload` in `src/api/routes/upload.py`: validates MIME + size before parsing (FR-001, FR-003), streams the file to a temp path, calls `IngestionService.ingest`, returns `UploadResponse`. Creates a session if `X-Session-Id` is absent; resolves it otherwise.
- [ ] T051 [US1] Implement `POST /ask` in `src/api/routes/ask.py`: validates body, resolves session, returns `StreamingResponse` (media type `text/event-stream`) iterating `QAService.answer` and formatting each `QAEvent` as an SSE frame; emits `event: error` + `Error` payload and closes cleanly when the retry budget is exhausted (FR-021).
- [ ] T052 [US1] Implement `POST /session/end` in `src/api/routes/session.py`: calls `SessionService.end`; returns 204; idempotent — a second call returns 404.
- [ ] T053 [US1] Wire everything in `src/main.py`: build settings, build observability, build factories, build services, register routes (`upload`, `ask`, `session`, plus `metrics` from T012), expose `app` for `uvicorn`.

**Checkpoint US1 (MVP)**: A user can `docker compose up`, upload a PDF, ask a question, watch tokens stream, see citations, and end the session. Quickstart §5 passes end-to-end.

---

## Phase 4: User Story 2 — Multi-turn follow-up questions (Priority: P2)

**Goal**: User asks follow-up questions whose answers depend on prior turns; transcript fetched via API.

**Independent Test**: `tests/integration/test_history_continuity.py` — ingest, ask "What is the termination period?", then ask "Can it be extended?", assert the second answer references the entity introduced in the first turn (heuristic: the second answer contains a token also present in the first, against a deterministic stub LLM that echoes its inputs).

- [ ] T054 [US2] Integration test `tests/integration/test_history_continuity.py`: two sequential `/ask` calls on the same session; assert the second prompt sent to the LLM stub includes the first turn's user + assistant content (use a `respx`-mocked LLM that records the messages payload).
- [ ] T055 [US2] Integration test `tests/integration/test_history_endpoint.py`: after two `/ask` calls, `GET /history/{sid}` returns 4 turns (2 user + 2 assistant) in chronological order with `citations` populated on assistant turns; another session's handle returns 404 (cross-session leakage check, FR-018).
- [ ] T056 [US2] Implement `GET /history/{session_id}` in `src/api/routes/history.py`: validates session ownership via the bearer token (any holder of the token can fetch any session they know the handle for — by design in v1), returns `HistoryResponse` shape from OpenAPI; 404 on missing/ended session.
- [ ] T057 [US2] In `src/services/qa.py`, ensure `QAService.answer` reads prior turns from `ConversationStore.get(session_id)` and threads them as `ChatMessage`s before the retrieved-context block, preserving role alternation (extend T049 if not already wired).

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
