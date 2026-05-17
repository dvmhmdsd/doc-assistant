# Implementation Plan: Doc Assistant (RAG-Powered Document Q&A)

**Branch**: `001-doc-assistant-rag` | **Date**: 2026-05-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-doc-assistant-rag/spec.md`

## Summary

Build a self-contained RAG-powered document assistant: a FastAPI service that ingests
PDF/DOCX files, indexes them in a session-scoped ChromaDB collection, and answers
natural-language questions via a streamed token feed from a swappable LLM provider
(Anthropic default, OpenAI alt). Each session is isolated by an unguessable handle
and persists until the user explicitly ends it. The single-tenant demo has no
global auth gate; the opaque `session_id` is the only access control. Answers
return alongside structured chunk citations. Six ADRs justify the architecture and tool
choices. A React + Tailwind SPA (feature 002) consumes the API and renders progressive
SSE streams.

## Technical Context

**Language/Version**: Python 3.11+ (backend), TypeScript 5.x + React 19 (frontend per
feature 002)

**Primary Dependencies**:
- Backend: `fastapi`, `uvicorn[standard]`, `pydantic` v2, `python-multipart`,
  `pymupdf` (PDF parser), `python-docx` (DOCX parser), `chromadb` (file-backed vector
  store), `sentence-transformers` (local embeddings, default), `openai`, `anthropic`,
  `tenacity` (bounded retry), `structlog` (structured logs), `prometheus-client`
  (local metrics endpoint).
- Frontend (feature 002, referenced here for contract alignment): React 19 +
  TypeScript + Vite + Tailwind CSS + native `EventSource` for SSE.

**Storage**: File-backed ChromaDB under `./chroma_data/` partitioned by session
(one collection per session handle). Uploaded files in a non-executable temp dir,
cleaned after ingestion. Conversation history in-memory per session.

**Testing**: `pytest` + `pytest-asyncio` (async tests), `httpx` (test client),
`respx` (HTTP mock for Anthropic/OpenAI calls), `pytest-cov` (coverage gate).
Streaming endpoints tested with chunk-by-chunk assertions; provider swaps validated
by contract tests against the five interfaces.

**Target Platform**: Linux container (Python 3.11 slim), runs on a single developer
machine or Docker host bound to `localhost:8000`. No external DB service.

**Project Type**: Web application (FastAPI backend + React SPA frontend) — Option 2.

**Performance Goals** (from spec SC-001/SC-002 + constitution Principle IV):
- 50-page PDF ingest < 30 s on laptop-class hardware (local embeddings).
- p95 first SSE token < 2 s from `/ask` acceptance.
- Vector search top-K < 200 ms for ≤ 10k chunks.
- Provider retry budget ≤ 5 s, ≤ 2 retries on transient errors.

**Constraints**:
- No LangChain / LlamaIndex / equivalents (Principle I).
- All cross-layer calls go through interface contracts (`DocumentParser`,
  `EmbeddingProvider`, `VectorStore`, `LLMClient`, `ConversationStore`).
- All tunables in `src/config.py` from environment; `.env.example` mirrors it.
- API keys never logged; secrets in env only.

**Scale/Scope**: Single-machine, single-tenant demo deployment with no global
auth gate (per-session isolation via opaque `session_id`). Multiple concurrent
sessions, each isolated. Hundreds of documents in aggregate per deployment;
no horizontal scale or multi-tenancy in v1.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | How this plan satisfies it |
|-----------|----------------------------|
| **I. Code Quality & Clean Architecture (NON-NEGOTIABLE)** | Layout under `src/` matches KICKOFF (parsers, chunker, embeddings, vector_store, llm, services, history, api). Five interfaces are defined in `src/<layer>/base.py`; concrete classes injected via factories. No LangChain. ruff + mypy required in CI. |
| **II. Test-First Discipline (NON-NEGOTIABLE)** | tasks.md (next phase) will list contract + integration + unit tests BEFORE implementation tasks. Streaming endpoint test asserts ≥ 2 SSE events arrive incrementally (not buffered). Each interface has a contract test that all implementations must pass. |
| **III. UX Consistency** | Single `/ask` SSE contract regardless of provider; three states (idle / processing / streaming) carried in event types; errors as `event: error` SSE frames with human-readable text. Conversation history forwarded on every follow-up. |
| **IV. Performance & Streaming Responsiveness** | Async FastAPI endpoints; `anthropic.AsyncAnthropic` + `openai.AsyncOpenAI`; embeddings batched; ChromaDB queries off the event loop via `run_in_threadpool`. Local `/metrics` endpoint exposes the four required timings (FR-023) so SC-001/SC-002 are measurable from one box. |
| **V. Configuration-Driven Extensibility** | `LLM_PROVIDER`, `EMBEDDING_PROVIDER`, `CHUNK_SIZE`, `CHUNK_OVERLAP`, `TOP_K_RESULTS` all in `src/config.py` + `.env.example`. New provider = implement interface + add factory branch; no service-layer edits. |

**Result**: PASS. No violations. Complexity Tracking table left empty.

## Project Structure

### Documentation (this feature)

```text
specs/001-doc-assistant-rag/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
│                       # (quickstart relocated to ../../docs/how-to/quickstart.md)
├── contracts/           # Phase 1 output (HTTP API + interface contracts)
│   ├── openapi.yaml
│   └── interfaces.md
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
src/
├── api/
│   ├── __init__.py
│   ├── app.py                  # FastAPI factory; mounts routes + middleware
│   ├── deps.py                 # auth gate, request ID, session resolver
│   ├── routes/
│   │   ├── upload.py
│   │   ├── ask.py              # SSE streaming endpoint
│   │   ├── history.py
│   │   ├── session.py          # explicit end-session
│   │   └── metrics.py          # /metrics (prometheus exposition)
│   └── errors.py
├── parsers/
│   ├── __init__.py
│   ├── base.py                 # DocumentParser ABC
│   ├── pdf.py                  # PyMuPDF
│   ├── docx.py                 # python-docx
│   └── factory.py              # parser_for(filename) -> DocumentParser
├── chunker/
│   ├── __init__.py
│   └── chunker.py              # TokenChunker (size + overlap), emits Chunks w/ locator
├── embeddings/
│   ├── __init__.py
│   ├── base.py                 # EmbeddingProvider ABC
│   ├── local.py                # sentence-transformers
│   ├── openai.py
│   └── factory.py
├── vector_store/
│   ├── __init__.py
│   ├── base.py                 # VectorStore ABC (session-scoped)
│   └── chroma.py               # ChromaDB adapter (one collection per session)
├── llm/
│   ├── __init__.py
│   ├── base.py                 # LLMClient ABC (async stream_chat)
│   ├── anthropic_client.py
│   ├── openai_client.py
│   ├── retry.py                # tenacity policy: <=2 retries, <=5s budget, transient-only
│   └── factory.py
├── services/
│   ├── __init__.py
│   ├── ingestion.py            # Facade: parse -> chunk -> embed -> store
│   ├── qa.py                   # Facade: retrieve -> prompt -> stream w/ citations
│   ├── sessions.py             # session lifecycle (create, get, end, isolate)
│   └── prompts.py              # prompt templates + citation formatter
├── history/
│   ├── __init__.py
│   ├── base.py                 # ConversationStore ABC
│   └── memory.py               # in-memory dict[session_id] -> list[Turn]
├── observability/
│   ├── __init__.py
│   ├── logging.py              # structlog config (request_id, never secrets)
│   └── metrics.py              # ingest_seconds, retrieval_seconds, ttft_seconds, ...
├── config.py                   # pydantic-settings; all env vars; .env loader
└── main.py                     # uvicorn entry; wires factories

tests/
├── contract/                   # one per interface
│   ├── test_parser_contract.py
│   ├── test_embedding_contract.py
│   ├── test_vector_store_contract.py
│   ├── test_llm_contract.py
│   └── test_history_contract.py
├── integration/
│   ├── test_ingestion_flow.py
│   ├── test_ask_streaming.py   # asserts multiple SSE events, citations present
│   ├── test_session_isolation.py
│   ├── test_session_end_purge.py
│   ├── test_provider_swap.py   # env-toggle, identical behaviour
│   └── test_auth_gate.py
└── unit/
    ├── test_chunker.py
    ├── test_pdf_parser.py
    ├── test_docx_parser.py
    ├── test_retry_policy.py
    └── test_citation_formatter.py

frontend/                       # populated by feature 002
└── (React + Tailwind SPA — see specs/002-chat-ui/plan.md when generated)

docs/
└── adr/
    ├── 0001-bespoke-rag-pipeline.md
    ├── 0002-chromadb-as-vector-store.md
    ├── 0003-pdf-docx-parser-choices.md
    ├── 0004-swappable-llm-embedding-providers.md
    ├── 0005-sse-streaming-approach.md
    ├── 0006-react-tailwind-client.md   # ties feature 002 back to 001's FR-014(f)
    └── 0007-fastapi-backend-choice.md   # Python+FastAPI vs Node (NestJS / Fastify)

Dockerfile
docker-compose.yml
.env.example
pyproject.toml                  # ruff, mypy, pytest config
README.md
```

**Structure Decision**: Web-application (Option 2). Backend lives at repository root
under `src/` (matches KICKOFF). Frontend (`frontend/`) is owned by feature 002 but the
top-level `docker-compose.yml` orchestrates both. The interface-driven layering inside
`src/` is the contract surface that satisfies Constitution Principle I and the
provider-swap criterion.

## Constitution Check (post-design re-evaluation)

Re-run after generating `research.md`, `data-model.md`, `contracts/`, and
`quickstart.md`. Verdict per principle:

| Principle | Post-design verdict |
|-----------|--------------------|
| **I. Code Quality & Clean Architecture** | PASS. `contracts/interfaces.md` enumerates exactly the five required interfaces + the chunker + facades; `src/` tree in this plan matches KICKOFF's layering. Factories are explicit. No LangChain referenced anywhere. |
| **II. Test-First Discipline** | PASS. `tests/` tree in this plan reserves a contract test per interface and an integration test that asserts incremental SSE frames. `/speckit.tasks` MUST emit the test tasks before their corresponding implementation tasks. |
| **III. UX Consistency** | PASS. `contracts/openapi.yaml` defines uniform error shape and SSE event types regardless of provider; `quickstart.md` shows identical commands under either provider. |
| **IV. Performance & Streaming Responsiveness** | PASS. `research.md` R-007 confirms async I/O on the hot path; `/metrics` (R-009) exposes the four required timings; retry budget (R-008) bounded at 5 s. |
| **V. Configuration-Driven Extensibility** | PASS. `data-model.md` `ProviderConfiguration` lists every tunable; `quickstart.md` §6 shows provider swap with no code change. |

**Result**: PASS, unchanged from pre-design check.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

(None — Constitution Check passed at both gates without violations.)
