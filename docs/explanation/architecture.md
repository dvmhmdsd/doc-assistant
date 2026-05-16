# Architecture

How the pieces fit together. This is the explanation pillar — read it
to understand WHY the system is shaped this way; the
[ADRs](../adr/README.md) cover the individual decisions; the [how-to
quickstart](../how-to/quickstart.md) covers running it.

## System view

```mermaid
flowchart LR
    user([Reviewer])

    subgraph browser["Browser"]
        spa["React + Tailwind SPA<br/>(feature 002)"]
    end

    subgraph container["doc-assistant container"]
        subgraph api["FastAPI API layer (src/api)"]
            mw[Request middleware<br/>+ request_id contextvar]
            authdep[require_bearer_token]
            routes["routes/<br/>upload • ask • history • session/end • metrics"]
            errh[AppError handler<br/>(typed Error schema)]
        end

        subgraph services["Service facades (src/services)"]
            ingest[IngestionService]
            qa[QAService]
            sess[SessionService]
            prompts[prompts.py<br/>+ format_citations]
        end

        subgraph core["Core layer (interfaces + impls)"]
            parsers[DocumentParser<br/>PdfParser • DocxParser]
            chunker[Chunker<br/>TiktokenTokenizer]
            embed[EmbeddingProvider<br/>Local • OpenAI]
            llm[LLMClient<br/>Anthropic • OpenAI]
            retry[bounded retry<br/>open_with_retry]
            vstore[VectorStore<br/>ChromaVectorStore]
            history[ConversationStore<br/>InMemory]
        end

        cfg[Settings<br/>pydantic-settings]
        obs[structlog logs<br/>Prometheus /metrics]
    end

    subgraph external["External (provider-side)"]
        anthropic[(Anthropic API)]
        openai[(OpenAI API)]
        hf[(HuggingFace<br/>model files)]
    end

    fs[(file-backed<br/>ChromaDB on volume)]

    user --> spa
    spa -- "HTTPS<br/>Bearer token" --> mw
    mw --> authdep --> routes
    routes --> errh
    routes -- "/upload"        --> ingest
    routes -- "/ask SSE"       --> qa
    routes -- "/session/end"   --> sess
    routes -- "/history/{sid}" --> history

    ingest --> parsers
    ingest --> chunker
    ingest --> embed
    ingest --> vstore

    qa --> embed
    qa --> vstore
    qa --> prompts
    qa --> llm
    qa --> history

    sess --> vstore
    sess --> history

    embed -.optional.-> openai
    embed -.local.-> hf
    llm --> retry
    retry --> anthropic
    retry --> openai
    vstore --> fs

    cfg -.injects.-> services
    cfg -.injects.-> core
    services -.emit.-> obs
    core -.emit.-> obs

    classDef ext fill:#fef3c7,stroke:#92400e
    classDef store fill:#dbeafe,stroke:#1e3a8a
    classDef cfg fill:#f3e8ff,stroke:#6b21a8
    class anthropic,openai,hf ext
    class fs store
    class cfg cfg
```

## Layering (top to bottom)

| Layer | Responsibility | Constraint |
|---|---|---|
| `api/` | HTTP surface: auth gate, request-id, route handlers, error → OpenAPI mapping | Imports services + Pydantic only |
| `services/` | Facades that orchestrate multi-step pipelines (ingest, qa, sessions) | Imports interfaces, never concrete provider classes |
| `core` (parsers, chunker, embeddings, vector_store, llm, history) | Interface definitions + concrete implementations | Concrete classes selected by factories, never imported across siblings |
| `models/` | Plain dataclasses (`Chunk`) shared by core layers | No behavior |
| `observability/` | structlog config, Prometheus registry | No domain logic |
| `config.py` | `Settings` singleton | Source of truth for tunables (Principle V) |

The **interface registry** (`contracts/interfaces.md`) is the only
cross-layer contract. Every cross-layer call goes through one of:

- `DocumentParser` — `parse(path) -> list[ParsedSegment]`
- `EmbeddingProvider` — `embed(texts) -> list[list[float]]`
- `VectorStore` — `add / search / drop_session`
- `LLMClient` — `stream_chat(messages) -> AsyncIterator[str]`
- `ConversationStore` — `append / get / drop_session`

Concrete implementations are wired by `lru_cache(maxsize=1)` provider
functions in `src/api/deps.py`. Every request sees the same singleton —
required for session isolation to work (a fresh `SessionService` per
request would lose every handle).

## Data flow at a glance

### Ingest

```
PDF/DOCX ──parser──► ParsedSegment[]
                       ▼
                     Chunker ──► Chunk[]
                       ▼
                   embedder ──► float[][]
                       ▼
                 ChromaVectorStore
                       ▼
            persists to /app/chroma_data (volume)
```

### Ask

```
question ──embedder──► query_vector
                          ▼
                 VectorStore.search(session_id, q, k=TOP_K_RESULTS)
                          ▼
              prompts.build_user_prompt(question, chunks)
                          ▼
              LLMClient.stream_chat ──► delta strings
                          ▼
        SSE frames: token{n} → citations → done
                          ▼
        ConversationStore.append(user turn, assistant turn)
```

## Why this shape

- **Interface-first** because the project must demonstrate OOP +
  design patterns clearly (see [ADR 0001](../adr/0001-bespoke-rag-pipeline.md)).
- **Factories at startup** so the service layer never knows what
  provider is in use (FR-010 / [ADR 0005](../adr/0005-swappable-llm-embedding-providers.md)).
- **File-backed ChromaDB inside the same image** so `docker compose up`
  is the whole product (FR-013 / [ADR 0003](../adr/0003-chromadb-as-vector-store.md)).
- **SSE for streaming** because it's exactly one-way, native to
  browsers, and trivial to test ([ADR 0006](../adr/0006-sse-streaming-approach.md)).
- **Async I/O + threaded sync libraries** so the event loop never
  blocks on disk or model inference (Constitution Principle IV).

## Related docs

- [ADR index](../adr/README.md) — the durable record of every major
  decision.
- [Sequence diagrams](./sequence-diagrams.md) — request-level flows for
  upload, ask, and session-end.
- [Quickstart](../how-to/quickstart.md) — run it locally in 5 minutes.
- [Feature 001 spec](../../specs/001-doc-assistant-rag/spec.md) — the
  contract.
- [Feature 001 plan](../../specs/001-doc-assistant-rag/plan.md) — the
  tech context.
