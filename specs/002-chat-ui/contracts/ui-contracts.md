# UI Contracts — Chat UI (002-chat-ui)

Three contract surfaces this feature owns:

1. **Backend HTTP routes the SPA consumes** (already specified in
   feature 001 — referenced here, not redefined).
2. **SSE frame contract** the SPA's parser must honor.
3. **Component interaction contracts** between modules in the SPA.

---

## 1. Backend routes consumed by the SPA

Authoritative source: [openapi.yaml](../../001-doc-assistant-rag/contracts/openapi.yaml).
The SPA consumes a strict subset:

| Method | Path | Purpose | SPA module |
|--------|------|---------|-----------|
| POST | `/upload` | Ingest document, get `session_id` | `src/api/upload.ts` |
| POST | `/ask` | Stream answer (SSE) | `src/api/ask.ts` |
| GET  | `/history/{session_id}` | Rehydrate transcript on reload | `src/api/history.ts` |
| POST | `/session/end` | Clear server-side session on "New Session" | `src/api/session.ts` |

The SPA does **not** consume `/healthz` or `/metrics`.

### Headers the SPA sends

| Header | Value | Notes |
|--------|-------|-------|
| `Content-Type` | `multipart/form-data` (POST /upload), `application/json` (everything else) | |
| `Accept` | `application/json` (or `text/event-stream` for `/ask`) | |
| `X-Session-Id` | `<session_id>` for the **second and later** `/upload` calls in the same session | Per OpenAPI |

The SPA does **not** send `Authorization`. The backend's auth dependency
treats same-origin browser requests as authenticated; this is a backend
contract change captured in T0xx (see `tasks.md`) and the ADR.

### Error shape

All non-2xx responses MUST conform to the existing
`Error` schema (`{code, message, request_id?}`). The SPA renders
`message` verbatim into the inline error surface (FR-013); it never
surfaces `code` to end users (logged to console for debugging only).

---

## 2. SSE frame contract for `/ask`

Reused from feature 001's `/ask` description. The SPA parser MUST
recognize exactly these event names:

| Event | Payload shape | Effect on state |
|-------|---------------|-----------------|
| `token` | `{ "text": string }` | Append `text` to the trailing assistant turn's `content` |
| `citations` | `Citation[]` | Set `citations` on the trailing turn (sent once, before `done`) |
| `done` | `{ "turn_id": string, "stopped": boolean }` | Finalize trailing turn (`complete` or `stopped`); reducer transitions to `ready` |
| `error` | `Error` (same schema as HTTP errors) | Reducer transitions to `error` with `message` rendered inline |

Parser MUST:

- Treat comment lines (`:keepalive`) as no-ops (used by FastAPI to keep
  the connection alive on slow LLM starts).
- Treat multi-line `data:` fields as JSON-after-concat (per SSE spec).
- Treat any unrecognized `event:` name as a no-op + console warning
  (forward-compat).
- Stop reading and dispatch `streamErrored` when the underlying
  `fetch` promise rejects (network drop) or `AbortController` fires.

### Stream lifecycle

```text
client                                     backend
  | -- POST /ask (json body) -------------> |
  | <--- 200 OK, text/event-stream -------- |
  | <--- event: token  data: {"text":"H"} - |
  | <--- event: token  data: {"text":"i"} - |
  | <--- event: citations  data: [...] ---- |
  | <--- event: done  data: {turn_id,...} - |
  | === stream closed ==================== |
```

Cancellation:

```text
  | -- AbortController.abort() ----------> | (TCP close)
  | === local reducer: state = "stopped" =
```

---

## 3. Component interaction contracts

### `UploadSurface` → reducer

```ts
type UploadCallbacks = {
  onStart(filename: string): void;        // dispatch uploadStarted
  onProgress(loaded: number, total: number): void; // dispatch uploadProgress
  onSuccess(resp: UploadResponse): void;  // dispatch uploadSucceeded
  onFailure(message: string): void;       // dispatch uploadFailed
};
```

Validation done in-component (FR-004) **before** dispatching `onStart`:

- File extension MUST be `.pdf` or `.docx`.
- File size MUST be ≤ `25 * 1024 * 1024` bytes.

Server-side rejections (415 / 413 / 400) are caught by `api/upload.ts`
and turned into `onFailure(message)`.

### `Composer` → reducer

```ts
type ComposerProps = {
  disabled: boolean;          // true iff state.kind === "streaming" || "uploading"
  placeholder: string;
  onSubmit(text: string): void;
};
```

Composer MUST:

- Reject empty / whitespace-only submissions client-side (no dispatch).
- Cap input at 4000 characters (matches `AskRequest.maxLength`).
- Show a visible "answering…" indicator from props when `disabled`.

### `Transcript` → DOM

- Each turn renders as `<li>` inside `<ul role="log" aria-live="polite">`.
- The currently-streaming assistant turn's text container has
  `data-streaming="true"`; the streaming reducer mutates `textContent`
  on that node by ref to avoid per-token React reconciliation across
  the list (Perf goal: 60 fps for 500-word answer).
- Auto-scroll: a `useLayoutEffect` scrolls the transcript to bottom on
  new tokens **only if** `scrollHeight - scrollTop - clientHeight < 80px`
  (the "near bottom" heuristic). Otherwise, render a `JumpToLatest`
  affordance (FR-011).

### `NewSessionButton` → reducer

```ts
type NewSessionProps = {
  onConfirm(): void;          // dispatch newSession
};
```

The button MUST render a confirmation step before dispatch (single
explicit action requirement of FR-018 is satisfied by the confirm
button counting as the one action; the trigger is a chevron/menu).

---

## 4. What is NOT a contract

- Visual design tokens (colors, exact spacing). Spec assumption defers
  these to implementation.
- Animation timings.
- Bundle splitting strategy beyond the 300 KB cap.

These may change without a contract version bump.
