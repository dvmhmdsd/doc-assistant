# ADR 0003: ChromaDB as the Vector Store

## Status

Accepted — 2026-05-16.

## Context

The product needs a vector store that:

- requires **no separate service** to keep `docker compose up` a single
  image (FR-013, SC-008);
- supports **metadata fields** so each chunk carries its `chunk_id`,
  `document_id`, page number (PDF) or section path (DOCX), and char
  range — required by FR-007a's citation contract;
- supports **per-session partitioning** so a query in session A can
  never return chunks stored in session B (FR-018);
- supports **clean deletion** of a session's data on explicit
  `/session/end` (FR-019).

It must also be embarrassingly easy to operate. v1 runs on a single
developer machine. We are not optimising for billion-vector recall or
horizontal scale.

## Decision

Use ChromaDB, file-backed via `chromadb.PersistentClient`, with one
collection per session.

Implementation choices encoded in `src/vector_store/chroma.py`:

- Collection name = `session_<sha256(session_id)[:16]>`. The raw
  (unguessable) session handle never appears on disk; the hashed
  prefix is stable and Chroma-collection-name-safe.
- Collection created with `metadata={"hnsw:space": "cosine"}` so
  similarity ranking matches what sentence-style embedding models were
  trained for. Default L2 would silently hurt recall.
- `search` returns `(Chunk, similarity)` where similarity ∈ `[0, 1]`,
  larger = more similar. The adapter converts Chroma's *distance* to
  similarity via `1 - distance` before exposing it. Without this
  conversion, every downstream consumer (`QAService` ranking,
  `Citation.score`) would order chunks backwards.
- All blocking Chroma calls run in worker threads via
  `asyncio.to_thread`. The FastAPI event loop never blocks on disk I/O.
- `drop_session` catches **only** `chromadb.errors.NotFoundError` to
  remain idempotent without swallowing every other error.

## Alternatives Considered

**FAISS.** Fast, in-process, mature. Rejected because it has no
first-class metadata storage and no persistence semantics — we would
have to bolt both on, and we would still own the per-session
partitioning.

**Qdrant / Weaviate.** Both excellent purpose-built vector databases.
Both require running a separate service (or embedding the engine into
the process, which neither does well for small deployments). They
contradict FR-013's "no separately managed external database service"
constraint.

**SQLite + `sqlite-vss` extension.** Tempting because SQLite is
ubiquitous. Rejected because the extension is a native binary that
needs platform-specific build / load handling, and it is much less
battle-tested for embedding workloads than Chroma.

**In-memory dict + cosine.** Fine for ≤ 1 000 chunks. Breaks at v1's
real corpus sizes (a 25 MB PDF can produce 10 k+ chunks), violates the
Repository abstraction by leaking storage choice into the service
layer.

## Consequences

**Positive.** Zero ops overhead (no second container, no port to
expose, no daemon to monitor). Metadata travels with vectors, so
citations can be reconstructed from a search result without a second
lookup. Per-session collections give us atomic, O(1) purge on
`/session/end`. The Python client is the most mature Chroma surface.

**Negative.** Chroma's API has drifted across the 0.x series — we pin
`>= 0.4.0` so `PersistentClient` and `get_or_create_collection(metadata=...)`
behave as documented. Recall is lower than purpose-built vector DBs at
extreme scale (single-machine deployment in v1 makes this irrelevant).
No built-in horizontal scaling; we accept that for v1 and would
reconsider if the deployment scope ever expanded.

## References

- `specs/001-doc-assistant-rag/research.md` — R-002.
- `specs/001-doc-assistant-rag/spec.md` — FR-013, FR-018, FR-019,
  FR-007a, SC-008.
- `specs/001-doc-assistant-rag/data-model.md` — collection naming
  scheme, metadata fields.
- `src/vector_store/chroma.py` — implementation.
