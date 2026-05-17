# Sequence Diagrams

Request-level flows for the four user-facing routes. Each diagram
matches a single HTTP call from the client; cross-layer hops are
annotated. Read alongside [architecture.md](./architecture.md) for the
system view and the [ADRs](../adr/README.md) for the why.

All diagrams use Mermaid.

---

## POST /upload — ingest a PDF or DOCX

```mermaid
sequenceDiagram
    autonumber
    actor client as Client
    participant api as FastAPI app
    participant sess as SessionService
    participant route as upload route
    participant ingest as IngestionService
    participant parser as parser_for
    participant chunker as Chunker
    participant embed as EmbeddingProvider
    participant vstore as ChromaVectorStore

    client->>api: POST /upload<br/>file=PDF/DOCX<br/>(opt) X-Session-Id

    alt X-Session-Id present
        api->>sess: resolve(session_id)
        sess-->>api: ok  (or 404 if missing/ended)
    else no header
        api->>sess: create_session()
        sess-->>api: new session_id<br/>(secrets.token_urlsafe(32))
    end

    api->>route: enter route handler
    route->>route: spool stream → /app/uploads_tmp/<br/>(enforce MAX_UPLOAD_BYTES, FR-003)
    alt exceeds cap
        route-->>client: 413 payload_too_large
    end

    route->>ingest: ingest(file_path, filename, mime, session_id)
    ingest->>parser: parser_for(filename, mime)
    alt unsupported type
        parser-->>client: 415 unsupported_media_type
    end
    parser-->>ingest: PdfParser or DocxParser

    ingest->>parser: parse(file_path)  (thread-offloaded)
    alt no extractable text
        parser-->>client: 400 bad_request (EmptyDocumentError)
    end
    parser-->>ingest: ParsedSegment[]

    ingest->>chunker: chunk(segments, document_id, session_id)
    chunker-->>ingest: Chunk[]

    ingest->>embed: embed([c.text for c in chunks])
    embed-->>ingest: float[][]

    ingest->>vstore: add(session_id, chunks, embeddings)
    vstore-->>ingest: ok  (cosine collection per session)
    ingest-->>route: IngestionResult<br/>(document_id, chunk_count, per-stage timings)

    route->>route: unlink temp file (FR-016)
    route-->>client: 200 UploadResponse<br/>{session_id, document_id, byte_size,<br/>chunk_count, ingested_timing_ms, ingested_at}
```

Key invariants visible above:

- The temp file is deleted in a `finally`, regardless of whether
  ingestion succeeded.
- The session id is established before any storage write, so a failed
  ingest can never poison a different session.
- Provider-specific errors get mapped to typed `AppError` subclasses
  before reaching the wire — clients never see raw stack traces
  (FR-011).

---

## POST /ask — streamed Q&A

```mermaid
sequenceDiagram
    autonumber
    actor client as Client
    participant api as FastAPI app
    participant sess as SessionService
    participant route as ask route
    participant qa as QAService
    participant history as ConversationStore
    participant embed as EmbeddingProvider
    participant vstore as VectorStore
    participant prompts as prompts.py
    participant llm as LLMClient
    participant retry as open_with_retry
    participant prov as Anthropic/OpenAI

    client->>api: POST /ask<br/>{session_id, question}
    api->>sess: resolve(session_id)
    sess-->>api: ok / 404
    api->>route: enter handler<br/>(StreamingResponse, text/event-stream)

    route->>qa: answer(session_id, question)
    qa->>history: get(session_id) [-20 turns]
    history-->>qa: prior turns

    qa->>embed: embed([question])
    embed-->>qa: [q_vector]

    qa->>vstore: search(session_id, q_vector, k=TOP_K_RESULTS)
    vstore-->>qa: [(chunk, similarity)]  (similarity ∈ [0,1])

    qa->>prompts: build_user_prompt(question, chunks)
    prompts-->>qa: composed prompt

    qa->>history: append(user turn)
    history-->>qa: ok

    qa->>llm: stream_chat(messages)
    llm->>retry: open_with_retry("anthropic"|"openai", ...)
    retry->>prov: open stream (network)
    alt transient (5xx/429/timeout/network)
        retry->>prov: retry (≤2, exp backoff, ≤5 s budget)
        retry-->>route: UpstreamUnavailable (502) if exhausted
    end
    prov-->>retry: stream handle
    retry-->>llm: stream

    loop tokens
        prov-->>llm: delta
        llm-->>qa: delta
        qa-->>route: QAEvent("token", {"text": delta})
        route-->>client: event: token<br/>data: {"text": "<delta>"}
    end
    Note over qa: time_to_first_token_seconds<br/>recorded on first yield

    qa-->>route: QAEvent("citations", Citation[])
    route-->>client: event: citations<br/>data: [{chunk_id, document_id,<br/>locator, score}, ...]

    qa->>history: append(assistant turn<br/>with citations + state="complete")

    qa-->>route: QAEvent("done", {turn_id, stopped: false})
    route-->>client: event: done<br/>data: {turn_id, stopped: false}

    alt exception mid-stream
        qa-->>route: raises AppError or unexpected
        route-->>client: event: error<br/>data: {code, message}
    end
```

Key invariants:

- `event: token` payload is **always** `{"text": delta}` (object), never
  a bare string. The OpenAPI spec enforces this; the SPA expects it.
- `event: citations` is emitted **exactly once**, **before** `done`.
- The user turn is persisted to history **before** the LLM stream starts
  so a concurrent `/history/{sid}` returns a coherent transcript.
- Retry is scoped to the connection-open ([ADR 0006](../adr/0006-sse-streaming-approach.md)).
  Once tokens start flowing, errors propagate to the `error` SSE frame
  rather than retrying (we can't replay a token stream).

---

## POST /session/end — purge a session

```mermaid
sequenceDiagram
    autonumber
    actor client as Client
    participant api as FastAPI app
    participant route as session route
    participant sess as SessionService
    participant vstore as ChromaVectorStore
    participant history as ConversationStore

    client->>api: POST /session/end<br/>{session_id}
    api->>route: enter handler
    route->>sess: end(session_id)

    sess->>sess: acquire registry lock
    alt session unknown / already ended
        sess-->>client: 404 not_found
    end
    sess->>sess: del registry[session_id]<br/>(release lock)

    sess->>vstore: drop_session(session_id)
    vstore->>vstore: delete_collection<br/>(idempotent: catches NotFoundError)
    vstore-->>sess: ok

    sess->>history: drop_session(session_id)
    history-->>sess: ok

    sess-->>route: ok
    route-->>client: 204 No Content
```

Idempotency story: the registry entry is removed first, so a concurrent
`/ask` or `/upload` referencing this handle will see a `NotFoundError`
during `resolve` before reaching the store layers. The vector store and
history store calls are themselves idempotent (vector store catches
`chromadb.errors.NotFoundError`; history store pops with a default), so
a half-completed `end` can be retried safely.

---

## GET /history/{session_id} — fetch transcript

```mermaid
sequenceDiagram
    autonumber
    actor client as Client
    participant api as FastAPI app
    participant route as history route
    participant sess as SessionService
    participant history as ConversationStore

    client->>api: GET /history/{session_id}
    api->>route: enter handler
    route->>sess: resolve(session_id)
    alt missing / ended
        sess-->>client: 404 not_found<br/>(prevents existence oracle)
    end
    sess-->>route: ok
    route->>history: get(session_id)
    history-->>route: ConversationTurn[]<br/>(locked snapshot)
    route-->>client: 200 HistoryResponse<br/>{session_id, turns: [...]}
```

No global auth gate in this single-tenant demo — anyone holding the
opaque `session_id` can read the transcript. This matches the v1
posture: a single internal user on a trusted laptop. Production
deploys MUST front the API with a reverse proxy / API gateway that
enforces authentication. Per-user accounts and per-session ACLs are
deferred (see Q1 / Q2 clarifications in the spec).

---

## Related

- [architecture.md](./architecture.md) — system-level view.
- [../adr/](../adr/README.md) — design decisions.
- [../how-to/quickstart.md](../how-to/quickstart.md) — run it locally.
- [`contracts/openapi.yaml`](../../specs/001-doc-assistant-rag/contracts/openapi.yaml) — wire contract.
