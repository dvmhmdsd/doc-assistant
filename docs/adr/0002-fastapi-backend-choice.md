# ADR 0002: Python + FastAPI for the Backend

## Status

Accepted — 2026-05-16.

## Context

The backend has to do four things well:

1. Stream LLM token deltas to a browser SSE client (FR-006, SC-002).
2. Run an interface-driven, layered codebase that demonstrates OOP
   patterns clearly (Constitution Principle I).
3. Speak fluently to the RAG ecosystem — embeddings, vector store,
   document parsers, LLM SDKs.
4. Be runnable as a single Docker image with no separate database
   service (FR-013, SC-008).

This ADR exists because the choice is significant enough that a reviewer asked "why not NestJS or Fastify?" — and the answer deserves to be in writing.

## Decision

Python 3.11+ with FastAPI for the entire backend. ASGI server:
`uvicorn[standard]`. Pydantic v2 + pydantic-settings for request
validation and configuration. `AsyncOpenAI` / `AsyncAnthropic` for LLM
clients. `sentence-transformers` for local embeddings.
`chromadb.PersistentClient` for the vector store. `structlog` for
JSON-line logs. `prometheus-client` for the `/metrics` endpoint.

FastAPI's `Depends()` system, combined with our own
`@lru_cache(maxsize=1)` provider functions in `src/api/deps.py`,
implements dependency injection without a heavyweight container —
which is exactly the shape Constitution Principle I expects (interfaces
+ factories + facades, no framework magic).

## Alternatives Considered

**NestJS (Node + TypeScript).** Strong OOP framework (decorators,
real DI container) and would unify language with the React client.
Rejected because the RAG ecosystem is materially thinner on Node:
`@xenova/transformers` is impressive but lags HuggingFace's Python
implementations; the official `chromadb` JS client is younger;
PyMuPDF / python-docx have no first-class equivalents. We would end
up either using lower-quality libs OR shelling out to Python anyway.
Net effect: more glue, less leverage.

**Fastify (Node + TypeScript).** Fast, minimal, mature streaming
support. No built-in DI — we would hand-roll the Strategy / Factory /
Repository / Facade plumbing the constitution requires, on a thinner
ML library stack. The pros (raw throughput) don't matter for a
single-machine demo.

**Flask / Django (Python).** Both default to synchronous request
handling. We would either fight the framework on every streaming
endpoint or run an async layer alongside. FastAPI is async-first and
makes the SSE story trivial.

**Starlette directly.** FastAPI is Starlette plus Pydantic validation
plus auto-generated OpenAPI plus a small DI helper. Dropping FastAPI
would mean rewriting all three. There is no reason to.

## Consequences

**Positive.** The RAG library ecosystem (PyMuPDF, python-docx,
chromadb, sentence-transformers, tiktoken, anthropic, openai) is all
first-class Python. Async-by-default means streaming endpoints are
trivial — `StreamingResponse` with an `async for` source generator
just works. Pydantic gives us request validation, OpenAPI schema
generation, and Settings-driven config in one cohesive surface.
`Depends()` composes with our factory pattern without needing a DI
container library.

**Negative.** Two-language stack with the React/Tailwind client: a
developer needs to be fluent in Python and TypeScript to ship a
feature end-to-end. We mitigate that with the OpenAPI spec as the
single source of truth on the wire. Python startup time is longer
than Node (a few seconds vs sub-second) — acceptable for a long-running
container. `mypy --strict` is more work than TypeScript's structural
typing — also a tradeoff we have explicitly bought into for the
interface discipline it enforces.

## References

- `specs/001-doc-assistant-rag/research.md` — R-006a.
- `specs/001-doc-assistant-rag/spec.md` — FR-014(g), SC-007.
- `.specify/memory/constitution.md` — Additional Constraints
  (technology stack lock).
- `KICKOFF.md` — initial scope brief.
- `pyproject.toml` — runtime dependency list.
