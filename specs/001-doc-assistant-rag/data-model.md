# Data Model: Doc Assistant

**Phase**: 1
**Branch**: `001-doc-assistant-rag`
**Source**: [spec.md](./spec.md) Key Entities

Everything below lives in process memory (sessions, history) or in file-backed
ChromaDB (chunks + embeddings). No relational DB.

---

## Session

The conversational thread. Created on first upload, destroyed only on explicit end
(per Q2 clarification: no idle TTL).

| Field | Type | Notes |
|-------|------|-------|
| `session_id` | `str` | `secrets.token_urlsafe(32)`. Unguessable. Primary key. |
| `created_at` | `datetime (UTC)` | For diagnostics/logs only. |
| `last_activity_at` | `datetime (UTC)` | Updated on every authenticated call referencing this session. Diagnostic only (no purge). |
| `document_ids` | `list[str]` | Documents ingested in this session. v1 expects ≤ 1 entry but the list keeps multi-doc as a future extension. |
| `collection_name` | `str` | ChromaDB collection backing this session: `session_<sha256(session_id)[:16]>`. |
| `history` | `list[ConversationTurn]` | Ordered. Append-only. |
| `is_ended` | `bool` | After explicit end: True → handle no longer resolves. |

**Lifecycle**:

```
[absent] --create_session(via /upload)--> [active]
[active] --record_turn(/ask)----------> [active]
[active] --POST /session/end----------> [ended -> purged from memory + chroma]
```

**Validation / invariants**:

- `session_id` MUST come from `secrets.token_urlsafe`; never derived from user input.
- After `is_ended=True`, the entry is removed; lookups MUST 401/404 (treat as
  not-found to avoid existence oracles).

---

## Document

A user-uploaded file after successful ingestion.

| Field | Type | Notes |
|-------|------|-------|
| `document_id` | `str` | Server-generated UUID. Stable handle returned by `/upload`. |
| `session_id` | `str` | FK → Session.session_id. |
| `filename` | `str` | Original filename (sanitized for display). |
| `mime_type` | `str` | `application/pdf` or `application/vnd.openxmlformats-officedocument.wordprocessingml.document`. |
| `byte_size` | `int` | After upload, ≤ 25 MB (FR-003). |
| `page_count` | `int \| None` | PDF only. |
| `chunk_count` | `int` | Number of chunks produced after chunking. |
| `ingested_at` | `datetime (UTC)` | When ingestion completed. |

**Validation**:

- `mime_type` rejected if not in the supported list (FR-001).
- `byte_size` rejected if > `MAX_UPLOAD_BYTES` (default 25 MB).
- `chunk_count == 0` → ingestion fails with a clear "file is not extractable" error
  (Edge Cases: scan-only PDFs).

---

## Chunk

A retrievable slice of a Document's text. Stored in ChromaDB; not in process memory.

| Field | Type | Notes |
|-------|------|-------|
| `chunk_id` | `str` | Deterministic: `<document_id>:<sequence_index>`. ChromaDB primary key. |
| `document_id` | `str` | FK → Document.document_id. |
| `session_id` | `str` | Redundant with collection scoping but recorded for defense-in-depth. |
| `sequence_index` | `int` | 0-based order within the document. |
| `text` | `str` | Raw chunk text (the content embedded). |
| `embedding` | `list[float]` | Stored by ChromaDB; not surfaced to API clients. |
| `page_number` | `int \| None` | PDF locator. 1-based. |
| `section_path` | `str \| None` | DOCX locator. e.g., `"Article 5 > §2"`. |
| `char_start` | `int` | Position in the original extracted text. |
| `char_end` | `int` | Position in the original extracted text. |

**Validation / invariants**:

- Every chunk MUST carry at least one of `page_number` (PDF) or `section_path`
  (DOCX) so it can be cited (FR-007a, Q1 clarification).
- `len(tokenize(text))` ≤ `CHUNK_SIZE` (default 500).
- Adjacent chunks share `CHUNK_OVERLAP` tokens (default 50).

---

## ConversationTurn

A single user question or assistant answer within a Session.

| Field | Type | Notes |
|-------|------|-------|
| `turn_id` | `str` | UUID. |
| `session_id` | `str` | FK → Session.session_id. |
| `role` | `Literal["user", "assistant"]` | Speaker. |
| `content` | `str` | The full text (for user turns: the question; for assistant turns: the streamed-and-then-finalised answer). |
| `citations` | `list[Citation] \| None` | Assistant turns only; `None` for user turns. |
| `created_at` | `datetime (UTC)` | Server time. |
| `state` | `Literal["complete", "stopped", "errored"]` | Assistant turns only. `complete` is the happy path. |

**Validation**:

- `role` MUST alternate user/assistant when present. The history fed to the LLM MUST
  end with the new user turn at QA time.
- For `state="stopped"` or `"errored"`, `content` MAY be a partial answer; the UI
  renders it with a visible marker (FR-010 in feature 002).

---

## Citation (embedded in ConversationTurn)

| Field | Type | Notes |
|-------|------|-------|
| `chunk_id` | `str` | The chunk used. |
| `document_id` | `str` | The chunk's parent document. |
| `locator` | `str` | Human-readable: `"page 12"` (PDF) or `"Article 5 > §2"` (DOCX). |
| `score` | `float` | Similarity score from the vector search (0..1-ish, provider-dependent). For diagnostics + ordering. |

---

## ProviderConfiguration (process-singleton, in-memory, env-derived)

| Field | Type | Source |
|-------|------|--------|
| `llm_provider` | `Literal["anthropic", "openai"]` | `LLM_PROVIDER` env |
| `embedding_provider` | `Literal["local", "openai"]` | `EMBEDDING_PROVIDER` env |
| `llm_model` | `str` | `LLM_MODEL` env (provider-specific default) |
| `embedding_model` | `str` | `EMBEDDING_MODEL` env (provider-specific default) |
| `chunk_size` | `int` | `CHUNK_SIZE` env (default 500) |
| `chunk_overlap` | `int` | `CHUNK_OVERLAP` env (default 50) |
| `top_k` | `int` | `TOP_K_RESULTS` env (default 5) |
| `max_upload_bytes` | `int` | `MAX_UPLOAD_BYTES` env (default 25 \* 1024 \* 1024) |
| `shared_token` | `str` (secret) | `APP_SHARED_TOKEN` env |
| `anthropic_api_key` | `str \| None` (secret) | `ANTHROPIC_API_KEY` env |
| `openai_api_key` | `str \| None` (secret) | `OPENAI_API_KEY` env |

**Validation**:

- If `llm_provider="anthropic"`, `anthropic_api_key` MUST be set; analogous for OpenAI.
- If `embedding_provider="openai"`, `openai_api_key` MUST be set.
- `APP_SHARED_TOKEN` MUST be set (non-empty) at startup. Server refuses to start
  without it.

---

## Relationships (summary)

```
Session 1───* Document 1───* Chunk
Session 1───* ConversationTurn ───* Citation ───1 Chunk
ProviderConfiguration  (singleton, derived from env)
```

---

## State transitions

### Session

```
absent --upload--> active --ask*--> active --end--> ended/purged
```

### Document (within a Session)

```
absent --upload--> uploading --parse-ok--> chunking --embed-ok--> ready
                              |                                    ^
                              +--parse-empty--> error (extractable=0)
absent --upload(oversize)----> rejected (never created)
```

### ConversationTurn (assistant)

```
created --first_token--> streaming --done---> complete
                                    --cancel-> stopped
                                    --error--> errored
```

---

## Storage layout

```
chroma_data/
├── chroma.sqlite3            # ChromaDB internal
└── <persist-dir>/
    └── (per-collection segment files)

uploads_tmp/                  # ephemeral; cleaned after ingestion (FR-016)
└── <session_id>/<upload_uuid>.<ext>
```

ChromaDB collection naming: `session_<sha256(session_id)[:16]>`. The full
session_id never appears on disk; only the hashed prefix.

In-process state (`SessionState`, history) lives in a single
`SessionRegistry` (Repository pattern) protected by an `asyncio.Lock` per session.
