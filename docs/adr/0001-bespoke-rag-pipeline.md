# ADR 0001: Bespoke RAG Pipeline (no LangChain / LlamaIndex / Haystack)

## Status

Accepted — 2026-05-16.

## Context

The Doc Assistant is, at its heart, a teaching artifact. The project
brief state that the codebase should *demonstrate*
Object-Oriented design and patterns (Strategy, Factory, Repository,
Facade) clearly enough for a reviewer to walk it end to end. That goal
sits next to a working product requirement (upload PDF/DOCX, ask
questions, get streamed answers grounded in the document with
citations).

We could have inherited a lot of these abstractions from an existing
framework. We chose not to.

## Decision

Build the retrieval pipeline ourselves, layer by layer, against explicit
interfaces. Concrete classes are injected via factories
(`make_llm_client`, `make_embedding_provider`, `parser_for`). The
service layer (`IngestionService`, `QAService`, `SessionService`)
orchestrates without importing provider-specific modules or branching on
`cfg.llm_provider`. The Strategy / Factory / Repository / Facade
patterns are the default response to "where does this code go?".

## Alternatives Considered

**LangChain.** Fastest path to a working demo. Rich integrations for
every embedding store, every LLM provider, every retriever variant.
Rejected because (a) it hides exactly the layering this project is
supposed to *showcase*, (b) it churns aggressively across minor versions
(public APIs renamed multiple times per quarter), and (c) it drags a
heavy transitive dependency tree that contradicts the constitution's
"minimal dependency footprint" rule.

**LlamaIndex.** Narrower than LangChain and arguably better at the
"index over documents" problem. Rejected for the same demo-the-patterns
reason: a `VectorStoreIndex` abstraction obscures the parser / chunker /
embedder / vector-store seams we want a reviewer to see.

**Haystack.** Closer to our preferred layering — pipeline components
with explicit inputs and outputs. Rejected because we already get that
shape from our own interfaces, and adding Haystack adds dependencies
(transformers, torch, telemetry) we do not need for our use case.

## Consequences

**Positive.** The codebase is auditable. Every step of ingestion and
retrieval lives in a small module that does one thing. Swapping a
provider is a class plus a factory branch plus a test. There is no
upstream API churn to chase. Reviewers can read top-down without
learning a framework first.

**Negative.** We pay for that clarity by writing things the frameworks
bundle: our own bounded-retry policy (`src/llm/retry.py`), our own
SSE framing, our own chunker with token-aware windowing, our own prompt
composer, our own session registry. None are large, but together they
are meaningful surface area we own forever. We also lose easy access to
the agent loops, tool-use harnesses, and routing helpers that LangChain
ships out of the box — but those are explicitly out of scope for v1.

## References

- `specs/001-doc-assistant-rag/research.md` — R-001.
- `.specify/memory/constitution.md` — Principle I (Code Quality &
  Clean Architecture, NON-NEGOTIABLE).
- `specs/001-doc-assistant-rag/spec.md` — FR-014(a), SC-007.
- `KICKOFF.md` — scope brief.
