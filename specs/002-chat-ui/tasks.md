---
description: "Task list for feature 002 — Chat UI (Upload + Streaming Q&A)"
---

# Tasks: Chat UI (Upload + Streaming Q&A)

**Input**: Design documents from `/specs/002-chat-ui/`

**Prerequisites**: plan.md, spec.md (US1–US5), research.md, data-model.md, contracts/ui-contracts.md

**Tests**: REQUIRED. Constitution Principle II (Test-First Discipline) is
NON-NEGOTIABLE — every implementation task has at least one preceding test
task that MUST fail before the implementation lands.

**Organization**: Tasks grouped by user story (US1…US5) so each story is
independently deliverable and testable. P1 stories (US1 + US2) together
form MVP — see Implementation Strategy.

## Format

`[TaskID] [P?] [Story?] Description with file path`

- **[P]**: parallelizable (different file, no incomplete-task dep)
- **[Story]**: US1…US5, required only inside user-story phases
- Setup / Foundational / Polish: no story label

## Path conventions

Web app layout already in repo: backend at `src/` (Python), frontend at
`frontend/` (TypeScript). All paths absolute or relative to repo root.

---

## Phase 1: Setup (frontend scaffold)

**Purpose**: Bring up the React 19 + Vite 8 + Tailwind 4 + TS 6 SPA
toolchain inside the existing `frontend/` directory (only `Dockerfile.dev`
currently lives there).

- [ ] T001 Create `frontend/package.json` pinning deps: `react@^19`, `react-dom@^19`, `clsx@^2`, `eventsource-parser@^3`; devDeps: `vite@^8`, `@vitejs/plugin-react` (latest matching Vite 8), `typescript@^6` (6.0.3 floor), `tailwindcss@^4`, `@tailwindcss/vite@^4`, `vitest@^4` (4.1.6 floor), `@vitest/coverage-v8`, `jsdom`, `@testing-library/react` (React 19-compatible), `@testing-library/jest-dom`, `@testing-library/user-event`, `msw@^2`, `openapi-typescript@^7`, `eslint@^9`, `typescript-eslint@^8`, `eslint-plugin-react-hooks` (latest), `eslint-plugin-react-refresh`, `prettier@^3`. Scripts: `dev`, `build`, `preview`, `test`, `typecheck`, `lint`, `format`, `gen:api`, `analyze`. Commit `package-lock.json` after first `npm install`.
- [ ] T002 [P] Create `frontend/vite.config.ts` registering `@vitejs/plugin-react` and `@tailwindcss/vite`; set `server.port=5173`, `server.host=true`, `server.proxy['/api']=process.env.VITE_API_BASE_URL ?? 'http://app:8000'` (dev only); `build.outDir='dist'`; `build.sourcemap=true`.
- [ ] T003 [P] Create `frontend/tsconfig.json` (strict, `target=ES2022`, `module=ESNext`, `moduleResolution=Bundler`, `jsx=react-jsx`, `verbatimModuleSyntax=true`, `noUncheckedIndexedAccess=true`, `exactOptionalPropertyTypes=true`, `lib=["ES2022","DOM","DOM.Iterable"]`); `frontend/tsconfig.node.json` for `vite.config.ts`.
- [ ] T004 [P] Create `frontend/index.html` with `<div id="root">` + `<script type="module" src="/src/main.tsx">`; `frontend/src/main.tsx` mounting `<App/>` via `createRoot`; `frontend/src/vite-env.d.ts` (`/// <reference types="vite/client" />`).
- [ ] T005 [P] Create `frontend/src/styles/tailwind.css` with `@import "tailwindcss";` and a `@theme { … }` block declaring the neutral color palette + base font stack (spec assumption — "clean, modern, minimal"); import in `main.tsx`.
- [ ] T006 [P] Create `frontend/eslint.config.js` (flat config) wiring `typescript-eslint@^8` recommended, `eslint-plugin-react-hooks` (rules-of-hooks + exhaustive-deps), `react-refresh/only-export-components`; ignore `dist/`, `coverage/`, `src/api/generated.ts`.
- [ ] T007 [P] Create `frontend/.prettierrc.json` (single-quote off, semi on, `trailingComma=all`, `printWidth=100`) and `frontend/.prettierignore` (`dist`, `coverage`, `src/api/generated.ts`, `package-lock.json`).
- [ ] T008 [P] Create `frontend/.gitignore` (`node_modules`, `dist`, `coverage`, `.vite`, `.eslintcache`).
- [ ] T009 [P] Create `frontend/src/App.tsx` stub returning a single `<main>` shell (no behavior yet) — placeholder to make the bundle compile end of Phase 1.

**Checkpoint**: `docker compose --profile dev run --rm frontend-dev npm run build` produces a `dist/` containing `index.html` + a near-empty bundle. No tests yet.

---

## Phase 2: Foundational (blocking prerequisites for ALL user stories)

**Purpose**: Wire the runtime container, backend auth bypass, typed
client, state machine skeleton, SSE parser, MSW fixtures, and bundle-size
guardrail. No user story can ship until this phase is green.

### Backend + container wiring

- [ ] T010 Backend: extend the bearer auth dependency in `src/api/deps.py` to accept unauthenticated requests when `Origin` (or `Referer` fallback) host matches the request's own host. Non-browser callers (no `Origin` and no `Referer`) still require bearer. Add unit tests in `tests/api/test_deps_same_origin.py` covering the four cases (same-origin no bearer = 200; mismatched origin no bearer = 401; no origin no bearer = 401; any origin + valid bearer = 200) — these tests MUST fail first.
- [ ] T011 Backend: mount the SPA via `app.mount("/", StaticFiles(directory=os.environ.get('SPA_DIST_DIR', '/app/frontend_dist'), html=True), name='spa')` in `src/api/app.py`, registered AFTER all API routers so `/upload`, `/ask`, `/history/{id}`, `/session/end`, `/healthz`, `/metrics` take precedence. Add `tests/api/test_static_mount.py` asserting `/` returns `index.html` and `/upload` still routes to the API handler — failing test first.
- [ ] T012 Extend the root `Dockerfile` `frontend-builder` stage with `WORKDIR /frontend`, `COPY frontend/package*.json ./`, `RUN npm ci --prefer-offline --no-audit --fund=false`, `COPY frontend ./`, `RUN npm run build`. In the runtime stage `COPY --from=frontend-builder /frontend/dist /app/frontend_dist`. No host Node required.
- [ ] T013 Update `.env.example` to add `# VITE_API_BASE_URL — dev-only proxy target; production SPA serves from same origin (leave empty)` and ensure `APP_SHARED_TOKEN` line documents that the SPA never sends it.
- [ ] T014 Author `docs/adr/0007-spa-same-origin-auth.md`: context (single-tenant demo), decision (same-origin bypass + bearer for non-browser callers), consequences (no token in bundle; multi-tenant deploy must re-evaluate), alternatives rejected (sessionStorage token, localStorage token, build-time embed, full auth disable).

### Frontend foundations

- [ ] T015 [P] Add `frontend/scripts/gen-api.mjs` invoking `openapi-typescript` against `../specs/001-doc-assistant-rag/contracts/openapi.yaml` → `src/api/generated.ts`; wire as `npm run gen:api`; commit the generated file (kept out of ESLint/Prettier via T006/T007 ignores).
- [ ] T016 [P] Implement `frontend/src/api/client.ts`: typed `fetchJson<T>(input, init)` wrapper around `fetch`. Sets `Accept: application/json`, attaches `Content-Type: application/json` when body is non-FormData, never attaches `Authorization`. Maps non-2xx to a typed `ApiError` exposing `code`, `message`, `requestId` from the `Error` schema. No retries (UI surfaces them).
- [ ] T017 [P] Implement `frontend/src/sse/types.ts`: discriminated union `SseEvent = TokenEvent | CitationsEvent | DoneEvent | ErrorEvent` mirroring ui-contracts.md §2.
- [ ] T018 [P] Implement `frontend/src/sse/parser.ts`: thin wrapper over `eventsource-parser`'s `createParser` that exposes `parseStream(stream: ReadableStream<Uint8Array>, onEvent: (e: SseEvent) => void, signal: AbortSignal): Promise<void>`. Validates each `event:` against the union and warns once (dev) on unknown event types.
- [ ] T019 [P] Implement `frontend/src/state/persistence.ts`: `loadSession(): string | null`, `saveSession(id: string): void`, `clearSession(): void`, all keyed on `"doc-assistant.session"` in `sessionStorage`. No `localStorage`, no cookies. Swallow `SecurityError` (sandboxed iframes) by returning `null`.
- [ ] T020 [P] Implement `frontend/src/state/session.ts`: `SessionState` discriminated union (kinds `empty | uploading | ready | streaming | error`) and `sessionReducer(state, action): SessionState` matching the transition table in data-model.md §2. Pure function; no side effects. Console-warns on disallowed transitions, never throws.
- [ ] T021 [P] Implement `frontend/src/state/transcript.ts`: `appendUserTurn`, `startAssistantTurn`, `appendTokenInPlace` (ref-mutating helper that returns the same array reference but mutates the trailing turn's `content`), `setCitations`, `finalizeTrailingTurn(state: "complete" | "stopped" | "errored")`.
- [ ] T022 [P] Setup `frontend/tests/mocks/handlers.ts` with MSW 2 handlers for `POST /upload`, `POST /ask` (streaming `Response`), `GET /history/:session_id`, `POST /session/end`, all built against types from `src/api/generated.ts`. Export `server` from `frontend/tests/mocks/server.ts` using `setupServer`.
- [ ] T023 [P] Configure `frontend/vitest.config.ts`: `environment: 'jsdom'`, `globals: false`, `setupFiles: ['./tests/setup.ts']`, `pool: 'threads'`, coverage v8. Create `frontend/tests/setup.ts` that starts/stops the MSW server and registers `@testing-library/jest-dom`.
- [ ] T024 [P] Add `frontend/scripts/check-bundle-size.mjs` reading `dist/assets/*.{js,css}`, gzipping in-memory, asserting JS ≤ 200 KB and CSS ≤ 100 KB (gzipped). Wire as `npm run analyze` and as a CI step.

**Checkpoint**: `docker compose run --rm app pytest` and `docker compose --profile dev run --rm frontend-dev npm test -- --run` both pass. SPA serves at `http://localhost:8000/` (empty shell, no behavior). Backend accepts SPA calls without a bearer.

---

## Phase 3: User Story 1 — Upload (Priority: P1) 🎯 MVP slice 1

**Goal**: Reviewer drags or picks a PDF/DOCX, sees progress, sees "ready".

**Independent test** (matches spec US1 Independent Test): open the SPA at
`http://localhost:8000/`, drag a sample PDF onto the upload surface,
observe progress indicator, then "ready" confirmation. Composer remains
disabled until "ready".

### Tests (write first; MUST fail before implementation)

- [ ] T025 [P] [US1] Reducer transition test `empty → uploading → ready` plus `uploading → error` in `frontend/tests/unit/state/session.upload.test.ts`. Asserts `sessionStorage` written exactly on success, cleared on `error.previous === empty`.
- [ ] T026 [P] [US1] Component test for `UploadSurface` in `frontend/tests/unit/components/UploadSurface.test.tsx`: idle render, drag-over visual state, client-side rejection of `.txt` (FR-004), client-side rejection of >25 MB (FR-004), progress indicator visible during upload, "ready" state announced via `aria-live` (FR-002, FR-016).
- [ ] T027 [P] [US1] Contract test `frontend/tests/contract/upload.test.ts` against MSW handlers: 200 returns `UploadResponse`, 413 surfaces `Error.message`, 415 surfaces `Error.message`, 400 surfaces `Error.message`. Asserts request carries `multipart/form-data` and **no** `Authorization` header.
- [ ] T028 [P] [US1] Backend integration test `tests/api/test_upload_same_origin.py`: POST `/upload` with `Origin: http://localhost:8000` and no bearer succeeds; with mismatched `Origin` and no bearer = 401. Validates T010's bypass on the real upload route.

### Implementation

- [ ] T029 [P] [US1] Implement `frontend/src/api/upload.ts`: `uploadDocument(file: File, sessionId: string | null, onProgress: (loaded: number, total: number) => void, signal: AbortSignal): Promise<UploadResponse>`. Uses `XMLHttpRequest` for progress events (the only browser API that exposes upload progress reliably). Sets `X-Session-Id` header iff `sessionId` non-null.
- [ ] T030 [P] [US1] Implement `frontend/src/components/UploadSurface.tsx`: drop zone (`dragover`/`drop` handlers), hidden `<input type="file" accept=".pdf,.docx">`, four visible states (empty / uploading / ready / error) driven by props from the reducer, inline error band rendering `Error.message` verbatim (FR-013), no popups. Client-side validation per FR-004 BEFORE dispatch.
- [ ] T031 [US1] Wire `UploadSurface` into `frontend/src/App.tsx`: `useReducer(sessionReducer, { kind: 'empty' })`, on file selection dispatch `uploadStarted`, call `uploadDocument`, dispatch `uploadProgress` / `uploadSucceeded` / `uploadFailed`. On success, `saveSession(resp.session_id)`.

**Checkpoint**: US1 fully functional. Browser refresh after upload still shows empty state (rehydration arrives in US3). Composer doesn't exist yet — that's fine; FR-005 prerequisite is enforced by the absence of any submit path.

---

## Phase 4: User Story 2 — Ask + Streaming (Priority: P1) 🎯 MVP slice 2

**Goal**: After "ready", user types a question, sees their message appear
immediately, watches the answer stream token-by-token, can cancel mid-stream.

**Independent test** (spec US2): with a ready document, submit a question,
observe (a) question in transcript immediately, (b) first answer token ≤
2 s, (c) text grows visibly, (d) composer re-enables on `done`. Cancel
mid-stream marks the trailing turn as "stopped".

### Tests (write first)

- [ ] T032 [P] [US2] Reducer test `ready → streaming → ready` and `streaming → ready (cancel)` and `streaming → error` in `frontend/tests/unit/state/session.streaming.test.ts`. Asserts user turn appended synchronously on `submitQuestion`; trailing turn becomes `stopped` on `streamCancelled`.
- [ ] T033 [P] [US2] SSE parser unit test `frontend/tests/unit/sse/parser.test.ts`: feeds canned bytes (token, multi-line `data:`, citations, comment `:keepalive`, done, error) and asserts dispatched `SseEvent` union members in order; asserts comments ignored; asserts unknown `event:` warns but does not throw.
- [ ] T034 [P] [US2] Streaming integration `frontend/tests/streaming/ask-incremental.test.ts`: MSW 2 streaming `Response` enqueues 3 token frames with `await sleep(10)` between, then citations + done. Drives real `api/ask.ts`. Asserts ≥ 2 `tokenAppended` dispatches arrive BEFORE `streamDone` AND the wall-clock gap between the first two `tokenAppended` dispatches > 0. (Satisfies constitution Principle II streaming gate on the consumer side.)
- [ ] T035 [P] [US2] Streaming cancel test `frontend/tests/streaming/ask-cancel.test.ts`: MSW streams forever; test calls `controller.abort()` after the first token; asserts reducer transitions to `ready` with trailing turn `state === "stopped"` and accumulated partial content preserved.
- [ ] T036 [P] [US2] Composer test `frontend/tests/unit/components/Composer.test.tsx`: empty/whitespace submission blocked (FR-007 corollary), 4001-char input truncated/blocked at 4000 (matches OpenAPI `AskRequest.maxLength`), `disabled` prop hides send + disables textarea + shows "answering…" indicator (FR-012), Enter submits, Esc dispatches cancel when streaming.
- [ ] T037 [P] [US2] Transcript test `frontend/tests/unit/components/Transcript.test.tsx`: scroll near bottom → auto-scroll on append; scroll up by > 80 px → `JumpToLatest` affordance appears and auto-scroll suppressed (FR-011); role attribution per turn (FR-006); streaming turn carries `data-streaming="true"`.

### Implementation

- [ ] T038 [P] [US2] Implement `frontend/src/api/ask.ts`: `streamAnswer(req: AskRequest, onEvent: (e: SseEvent) => void, signal: AbortSignal): Promise<void>`. `fetch` POST with `Accept: text/event-stream`, body JSON; reads `response.body!.getReader()`, passes chunks to `sse/parser.ts`. On `signal.aborted` propagates `AbortError` to caller.
- [ ] T039 [P] [US2] Implement `frontend/src/components/Composer.tsx`: controlled `<textarea>`, character counter, send button (`type="submit"`), cancel button (`type="button"`, visible only while streaming). Form `onSubmit` calls `props.onSubmit(text)`.
- [ ] T040 [P] [US2] Implement `frontend/src/components/Turn.tsx`: renders `<li>` with role-attributed styling. The streaming variant exposes a `ref` on the text container so `transcript.appendTokenInPlace` can mutate `textContent` directly during streaming (Perf goal: 60 fps for 500-word answer).
- [ ] T041 [P] [US2] Implement `frontend/src/components/Transcript.tsx`: `<ul role="log" aria-live="polite">` with `useLayoutEffect`-based near-bottom auto-scroll heuristic (threshold 80 px); renders `JumpToLatest` when user scrolled away.
- [ ] T042 [P] [US2] Implement `frontend/src/components/JumpToLatest.tsx`: sticky button bottom-right, dispatches `scrollIntoView` on the latest turn ref.
- [ ] T043 [P] [US2] Implement `frontend/src/components/CitationList.tsx`: renders `Citation[]` with `locator` + truncated score (1 decimal). No external links — citations are informational only.
- [ ] T044 [US2] Wire Composer + Transcript into `App.tsx`: on submit dispatch `submitQuestion`, create `AbortController`, call `streamAnswer`, route each `SseEvent` to the reducer (`tokenAppended` / `citationsReceived` / `streamDone` / `streamErrored`). On cancel button click call `state.controller.abort()`.

**Checkpoint**: MVP (US1 + US2) shippable. Upload → ask → stream → cancel all work end-to-end inside `docker compose up`.

---

## Phase 5: User Story 3 — Multi-turn conversation (Priority: P2)

**Goal**: Multiple turns render in order; rehydration on refresh.

**Independent test** (spec US3): after one answer, send a pronoun-bearing
follow-up; new exchange appended in order; refresh tab → transcript
rehydrated; Compose composer still works.

### Tests (write first)

- [ ] T045 [P] [US3] Reducer test `frontend/tests/unit/state/session.multiturn.test.ts`: three submit→stream→done cycles produce six turns (3 user + 3 assistant) in chronological order; `state.kind === "ready"` between each.
- [ ] T046 [P] [US3] Rehydration contract test `frontend/tests/contract/history.test.ts`: MSW serves `GET /history/:id` with two user + two assistant turns; reducer dispatch `rehydrated` produces a `ready` state with transcript populated and `controller` absent.
- [ ] T047 [P] [US3] Transcript multi-turn test `frontend/tests/unit/components/Transcript.multiturn.test.tsx`: 20-turn transcript renders without overlap, role markers visible on each (FR-006), no `aria` collisions.

### Implementation

- [ ] T048 [P] [US3] Implement `frontend/src/api/history.ts`: `fetchHistory(sessionId): Promise<HistoryResponse>`. Maps `ConversationTurn[]` to internal `Turn[]` (`role`, `content`, `citations`, `createdAt`, `state = "complete"`, `id = turn_id`).
- [ ] T049 [P] [US3] Refine `Turn.tsx` + `Transcript.tsx` styling (separation, role pills, timestamps). No new logic.
- [ ] T050 [US3] In `App.tsx`, on mount: read `loadSession()`; if non-null, call `fetchHistory(id)`; on success dispatch `rehydrated(resp)`; on 404 / network error dispatch `rehydrateFailed` and call `clearSession()`.

**Checkpoint**: refresh restores transcript; pronoun-bearing follow-ups land in order.

---

## Phase 6: User Story 4 — Recover from errors (Priority: P2)

**Goal**: Upload failures, mid-stream drops, provider errors all surface
inline with retry; no stack traces.

**Independent test** (spec US4): kill the connection or use an invalid
provider key; UI shows a recoverable error message with retry and
preserved history; zero raw stack traces / provider IDs in the surface.

### Tests (write first)

- [ ] T051 [P] [US4] Reducer error-snapshot test `frontend/tests/unit/state/session.error.test.ts`: `streaming → error` snapshots `previous = ready(<transcript_at_failure>)`; `retry()` returns to `previous` exactly.
- [ ] T052 [P] [US4] `ErrorInline` component test `frontend/tests/unit/components/ErrorInline.test.tsx`: renders `Error.message` verbatim; never renders `Error.code` to the DOM; renders a "Retry" button when `onRetry` prop supplied.
- [ ] T053 [P] [US4] Error path contract test `frontend/tests/contract/error-paths.test.ts`: MSW replies 401/404/413/415/502 for `/upload` and `/ask`; client surfaces each `message` and never logs `Authorization` header (regression guard for FR-024/FR-025).
- [ ] T054 [P] [US4] Streaming-drop test `frontend/tests/streaming/ask-drop.test.ts`: MSW handler closes the stream after the first token with no `done` frame; reducer transitions to `error`; trailing turn marked `errored` with partial content preserved; "Retry" affordance appears.

### Implementation

- [ ] T055 [P] [US4] Implement `frontend/src/components/ErrorInline.tsx`: renders inside the chat surface (not a popup, not a toast); receives `{ message: string; onRetry?: () => void }`. `aria-live="assertive"`.
- [ ] T056 [P] [US4] Add retry affordance to `UploadSurface` (preserves file selection across retry) and to a failed assistant `Turn` (re-issues the prior `submitQuestion` with the same text).
- [ ] T057 [US4] Wire retry actions in `App.tsx`: on `state.kind === "error"` render `ErrorInline` with appropriate `onRetry` callback. Failure of `POST /session/end` (during "New Session") surfaces inline but still resets local state per FR-018.

**Checkpoint**: every failure mode demoable; no stack traces or provider IDs ever rendered.

---

## Phase 7: User Story 5 — Small screen (Priority: P3)

**Goal**: SPA usable at ≤ 768 px viewport with no horizontal scroll and
no obscured composer.

**Independent test** (spec US5): resize browser to ~600 px; upload + send
+ stream all work without horizontal scrolling and without the composer
disappearing.

### Tests (write first)

- [ ] T058 [P] [US5] Responsive component test `frontend/tests/unit/components/responsive.test.tsx`: render `App` at `window.innerWidth = 600`; assert `document.body.scrollWidth === document.body.clientWidth` (no horizontal scrollbar); composer remains in DOM and not `display: none`.

### Implementation

- [ ] T059 [US5] Apply Tailwind responsive utilities across `App.tsx`, `UploadSurface.tsx`, `Composer.tsx`, `Transcript.tsx`: drop multi-column at `md:`, stack vertically below `md:`, composer is `sticky bottom-0` on small viewports.

**Checkpoint**: SC-007 holds (1440 px → 600 px reflow reachable, no horizontal scrollbar).

---

## Phase 8: Polish & Cross-Cutting

**Purpose**: New-session action, accessibility sweep, docs, bundle-size
verification, final green run.

- [ ] T060 [P] Implement `frontend/src/api/session.ts`: `endSession(sessionId: string): Promise<void>` calling `POST /session/end`. Treat 404 as success (idempotent on the server already).
- [ ] T061 [P] Implement `frontend/src/components/NewSessionButton.tsx`: confirm step before dispatch; calls `endSession` then `dispatch(newSession())`; failure surfaces inline but does not block the local reset (FR-018).
- [ ] T062 [P] Add `frontend/src/components/SessionIndicator.tsx` showing current document filename + a slot for `NewSessionButton`.
- [ ] T063 [P] Keyboard-walkthrough test `frontend/tests/unit/keyboard.test.tsx`: RTL `userEvent` drives Tab order: upload → composer → send → cancel → copy → new-session. Enter submits; Esc cancels streaming; Ctrl/Cmd+K opens new-session confirm. Asserts SC-006 path.
- [ ] T064 [P] Implement "Copy answer" affordance on assistant turns (FR-019): one-click button using `navigator.clipboard.writeText` on the rendered text (plain text only, no markup).
- [ ] T065 [P] Add `aria-live="polite"` on streaming turn container, `aria-live="assertive"` on `ErrorInline`, visible `focus-visible:ring-2` on all controls (FR-016).
- [ ] T066 [P] Add safe-render guard for assistant content in `Turn.tsx`: render `content` only as `textContent` / React text node — never `dangerouslySetInnerHTML` (FR-017). Add a unit test that asserts `<script>alert(1)</script>` in `content` renders as literal text.
- [ ] T067 Run `npm run build && npm run analyze` inside `frontend-dev`; verify gzipped JS ≤ 200 KB + CSS ≤ 100 KB. If over, eliminate dead deps before any other optimization.
- [ ] T068 Update `README.md` at repo root: add a "Chat UI" section linking to `http://localhost:8000/` after `docker compose up`; explicitly delete any `npm run dev` / `uvicorn …` instructions from start-path docs (FR-022).
- [ ] T069 Update `quickstart.md` (already created) with the final dev workflow notes once T010–T012 are in place.
- [ ] T070 Add a GitHub Actions step (or extend the existing workflow) to run `docker compose run --rm app pytest` AND `docker compose --profile dev run --rm frontend-dev npm test -- --run` AND `npm run analyze`. Failures block merge per constitution.
- [ ] T071 Final integration run: `docker compose up --build`, walk the five user stories manually inside Chromium, confirm SC-001 (≤ 60 s first end-to-end), SC-002 (first token ≤ 2 s p95), SC-005 (no stack traces visible). Record observed timings in the PR description.

---

## Dependencies

```text
Phase 1 (Setup, T001–T009) ─┐
                            └──► Phase 2 (Foundational, T010–T024)
Phase 2 ──► Phase 3 (US1, T025–T031)  ──┐
       ──► Phase 4 (US2, T032–T044)  ──┤
       ──► Phase 5 (US3, T045–T050)  ──┤──► Phase 8 (Polish, T060–T071)
       ──► Phase 6 (US4, T051–T057)  ──┤
       ──► Phase 7 (US5, T058–T059)  ──┘
```

- **Setup → Foundational**: strict (Phase 2 needs the toolchain Phase 1 lays down).
- **Foundational → User Stories**: strict (auth bypass, static mount, typed client, reducer, parser, MSW server all required).
- **User Stories**: US1 and US2 together form MVP and are best done in order (US2 reuses the reducer + sessionStorage from US1). US3 needs US2's `Turn`/`Transcript`. US4 cuts across US1/US2 surfaces — can start after US2 lands. US5 is pure CSS on top of US1–US4 and can ship last.
- **Polish**: depends on all user-story phases.

## Parallel execution examples

- **Phase 1 setup** (post-T001): T002, T003, T004, T005, T006, T007, T008, T009 all `[P]` — open 8 files independently.
- **Phase 2 foundational frontend block**: T015, T016, T017, T018, T019, T020, T021, T022, T023, T024 all `[P]` — independent files; T010–T014 backend/container work parallelizes with the frontend block.
- **Phase 3 US1 tests**: T025, T026, T027, T028 in parallel; **then** T029, T030 in parallel; **then** T031 (depends on T029 + T030 + reducer).
- **Phase 4 US2 tests**: T032, T033, T034, T035, T036, T037 in parallel; **then** T038, T039, T040, T041, T042, T043 in parallel; **then** T044.
- **Phase 8 polish**: T060, T061, T062, T063, T064, T065, T066 all `[P]`.

## Independent test criteria per story

- **US1**: upload PDF → see "ready". No composer required to verify.
- **US2**: with US1 done, type → submit → ≥ 2 tokens appear incrementally → cancel marks "stopped". Streaming-integration test (T034) is the automated proof.
- **US3**: refresh tab after upload → transcript repopulates from `GET /history/{id}`.
- **US4**: kill backend mid-stream → "Retry" affordance appears, transcript preserved, no stack trace.
- **US5**: resize to 600 px → no horizontal scrollbar, composer reachable.

## Implementation strategy — MVP-first

1. **MVP = US1 + US2.** Land Phase 1 + Phase 2, then Phase 3 + Phase 4. At that point a reviewer can upload a PDF and watch a streamed answer. This is the demo headline.
2. **First incremental enhancement = US3 (rehydrate) + US4 (errors).** Both depend on the MVP surfaces existing.
3. **Final polish = US5 (responsive) + Phase 8 (a11y, copy, new-session, bundle, docs).**
4. **Constitution gates re-checked at every merge**: lint + typecheck + pytest + npm test + bundle-size analyze. Failures block.
