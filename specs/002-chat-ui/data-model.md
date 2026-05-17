# Phase 1 — SPA Data Model (002-chat-ui)

Frontend-only entities. The backend data model is unchanged and lives in
`specs/001-doc-assistant-rag/data-model.md`. This file describes the
TypeScript shapes the SPA owns plus the state machine that ties them
together.

---

## 1. Entities

### 1.1 `Turn`

A single message in the transcript.

| Field | Type | Notes |
|------|------|-------|
| `id` | `string` (UUID) | Server-assigned for assistant turns (from SSE `done` event). Client-generated `crypto.randomUUID()` for user turns. |
| `role` | `"user" \| "assistant"` | Drives styling + role attribution (FR-006). |
| `content` | `string` | Plain text. Streaming turns mutate this in place; only the **last** assistant turn may be mutated. |
| `citations` | `Citation[] \| null` | Populated from the `citations` SSE frame; never populated for user turns. |
| `state` | `"sent" \| "streaming" \| "complete" \| "stopped" \| "errored"` | Per spec entity definition. |
| `createdAt` | `string` (ISO 8601) | Source: server for rehydration; `new Date().toISOString()` for client-generated turns. |

Validation:

- `content` MUST be non-empty when `state === "complete" \| "stopped"`.
  An assistant turn that ended with zero tokens MUST be `errored`.
- A turn that is `streaming` MUST be the last turn in the transcript
  (invariant enforced by the reducer).
- `state === "stopped"` requires a visible "stopped" marker in the
  rendered turn (FR-010).

### 1.2 `Citation`

Renders next to assistant turns.

| Field | Type | Notes |
|------|------|-------|
| `chunk_id` | `string` | Pass-through from OpenAPI schema. |
| `document_id` | `string` (UUID) | Pass-through. |
| `locator` | `string` | Human-readable ("page 12", "Article 5 > §2"). |
| `score` | `number` (float, 0–1) | Similarity, larger = more similar. |

Validation: trust the server (already validated by FastAPI). The SPA
treats this as a read-only DTO.

### 1.3 `DocumentMeta`

The single ingested document for the session.

| Field | Type | Notes |
|------|------|-------|
| `documentId` | `string` (UUID) | From `UploadResponse`. |
| `filename` | `string` | Displayed in the Session Indicator. |
| `byteSize` | `number` | Used for the "size" hint on rejection messages. |
| `chunkCount` | `number` | Cosmetic only (debug strip). |
| `pageCount` | `number \| null` | DOCX may be null. |
| `ingestedAt` | `string` (ISO 8601) | |

### 1.4 `SessionState` (discriminated union — the SPA's root state)

```ts
type SessionState =
  | { kind: "empty" }
  | { kind: "uploading"; filename: string; progress?: number }
  | { kind: "ready";     sessionId: string; document: DocumentMeta; transcript: Turn[] }
  | { kind: "streaming"; sessionId: string; document: DocumentMeta; transcript: Turn[]; controller: AbortController }
  | { kind: "error";     message: string; previous?: SessionState };
```

Invariants:

- `transcript` is append-only except for in-place mutation of the
  trailing assistant turn while `kind === "streaming"`.
- `controller` is non-null only in `streaming`. Transitioning out of
  `streaming` MUST call `controller.abort()` if the transition is a
  user-initiated cancel.
- `previous` exists only in `error` and only when the error is
  recoverable (so a retry can restore prior context — FR-014).

### 1.5 `PersistedSession`

The only thing the SPA writes to `sessionStorage`.

```ts
type PersistedSession = {
  sessionId: string;
  // No transcript, no document meta — rehydration round-trips
  // GET /history/{sessionId} on next load.
};
```

Key: `"doc-assistant.session"`. Value: `JSON.stringify(persisted)`.

---

## 2. State machine

Allowed transitions (`event → from → to`):

| Event | From | To | Side effects |
|-------|------|----|--------------|
| `uploadStarted(filename)` | `empty` \| `ready` \| `error` | `uploading` | none |
| `uploadProgress(p)` | `uploading` | `uploading` (progress updated) | none |
| `uploadSucceeded(resp)` | `uploading` | `ready` | persist session id to `sessionStorage` |
| `uploadFailed(msg)` | `uploading` | `error` (with `previous = empty`) | none |
| `rehydrated(resp)` | `empty` | `ready` | none (handle already in `sessionStorage`) |
| `rehydrateFailed()` | `empty` | `empty` | clear `sessionStorage` |
| `submitQuestion(q)` | `ready` | `streaming` | append user `Turn` (sent), create AbortController, open `POST /ask` |
| `tokenAppended(t)` | `streaming` | `streaming` | mutate trailing assistant `Turn.content` |
| `citationsReceived(c)` | `streaming` | `streaming` | set trailing turn `citations` |
| `streamDone(turnId)` | `streaming` | `ready` | finalize trailing turn (`state = "complete"`, `id = turnId`) |
| `streamCancelled()` | `streaming` | `ready` | `controller.abort()`, finalize trailing turn (`state = "stopped"`) |
| `streamErrored(msg)` | `streaming` | `error` (`previous = ready snapshot`) | finalize trailing turn (`state = "errored"`) |
| `retry()` | `error` | `previous` | none (re-enter previous state) |
| `newSession()` | any except `uploading` | `empty` | call `POST /session/end` (best-effort; failure surfaces inline but state still resets), clear `sessionStorage` |

Disallowed transitions are no-ops that log a warning to the console (dev
only) — the reducer never throws. This matches FR-013 (no raw error
surface) and FR-018 (one obvious action that always succeeds locally).

---

## 3. Storage / persistence rules

- The SPA writes `sessionStorage` **only** on `uploadSucceeded` and
  clears it on `rehydrateFailed`, `newSession`, and on any
  `error.previous === empty` transition.
- The SPA never writes `localStorage`, never writes cookies, and never
  writes `IndexedDB`.
- No request the SPA issues carries `Authorization` (FR-025). All
  requests carry `Content-Type: application/json` (except `/upload`,
  which is `multipart/form-data`) and `Accept: application/json` (or
  `text/event-stream` for `/ask`).

---

## 4. Relationship to backend entities

- `Turn.id` (assistant role) ↔ backend `ConversationTurn.turn_id`.
- `Citation.*` is structurally identical to backend `Citation`.
- `DocumentMeta` is a strict subset of backend `UploadResponse`.
- `PersistedSession.sessionId` ↔ backend session handle.

No new backend fields are introduced.
