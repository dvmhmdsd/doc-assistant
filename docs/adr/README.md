# Architecture Decision Records

This directory captures the major design decisions behind the Doc
Assistant. Each ADR follows the same four-section template — Context,
Decision, Alternatives Considered, Consequences — required by FR-014
in `specs/001-doc-assistant-rag/spec.md` and verified by SC-007.

ADRs are part of the **Explanation** pillar of the Diataxis framework:
they capture the "why" behind decisions, not the "what". Read them when
you want to understand a tradeoff, propose a change, or onboard onto
the codebase.

## Index

| # | Decision | One-line summary |
|---|---|---|
| [0001](./0001-bespoke-rag-pipeline.md) | Bespoke RAG pipeline | Why we wrote the retrieval pipeline ourselves instead of using LangChain / LlamaIndex / Haystack. |
| [0002](./0002-fastapi-backend-choice.md) | Python + FastAPI backend | Why not NestJS or Fastify; what the RAG ecosystem buys us in Python. |
| [0003](./0003-chromadb-as-vector-store.md) | ChromaDB as the vector store | File-backed Chroma with one collection per session, cosine metric, distance→similarity conversion. |
| [0004](./0004-pdf-docx-parser-choices.md) | PyMuPDF + python-docx parsers | Fast page-aware PDF extraction, heading-stack section paths for DOCX. |
| [0005](./0005-swappable-llm-embedding-providers.md) | Swappable LLM + embedding providers | Two ABCs + factory functions; provider chosen by `.env`, never by service-layer branching. |
| [0006](./0006-sse-streaming-approach.md) | SSE for /ask streaming | `text/event-stream` with four frame types; mid-stream errors emit an `event: error` frame instead of dropping the connection. |

The ordering follows the build-up of the system: language/framework
before storage before parsers before provider strategy before transport.
Each later ADR assumes the choices above it.

## Cross-References

- Required by [`specs/001-doc-assistant-rag/spec.md`](../../specs/001-doc-assistant-rag/spec.md) — FR-014(a–f).
- Verified by SC-007 — every major design choice has a record with the
  four mandatory sections.
- Background research lives in
  [`specs/001-doc-assistant-rag/research.md`](../../specs/001-doc-assistant-rag/research.md);
  each ADR points back to the relevant `R-***` entry.

## Adding a new ADR

1. Number sequentially: `00NN-short-slug.md`.
2. Use the four-section template (Status / Context / Decision /
   Alternatives Considered / Consequences). Optional `## References`
   at the end.
3. Update this index.
4. If the new ADR supersedes an older one, change the older ADR's
   Status to `Superseded by ADR-NNNN` and link both directions.
