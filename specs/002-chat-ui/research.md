# Phase 0 Research — Chat UI (002-chat-ui)

All Technical Context items resolved. Each section below records the
**Decision**, **Rationale**, and **Alternatives considered**.

---

## 1. Streaming transport in the browser

**Decision**: Consume `/ask` via `fetch` POST + `response.body.getReader()`
(`ReadableStream`), with `AbortController` for cancel. Parse SSE frames
using the `eventsource-parser` package. No `EventSource`, no WebSocket.

**Rationale**:

- `/ask` is `POST` with a JSON body (per `openapi.yaml`); `EventSource` is
  GET-only and cannot send headers or bodies.
- `AbortController.abort()` halts both the network read and the parser,
  satisfying FR-010 (cancel preserves partial answer, then marks "stopped").
- `eventsource-parser` is the de-facto SSE parser used by OpenAI's own JS
  SDK; correctly handles multi-line `data:`, `event:`, `id:`, comments
  (`:keepalive`), and BOM. Hand-rolling this would be a guaranteed
  reviewer flag (FR-013 — no malformed-stream regressions).
- Works behind a future reverse proxy without changing the FE.

**Alternatives considered**:

- *Native `EventSource`*: rejected (GET-only, no headers, no body).
- *WebSocket*: rejected (full duplex unneeded; new server upgrade path;
  heavier infra; clashes with FastAPI streaming primitive already chosen
  in feature 001).
- *HTTP chunked transfer without SSE framing*: rejected (loses
  `event: token | citations | done | error` semantics already used by the
  backend; FE would need to invent a frame protocol).

**Backend impact**: none — `/ask` already streams SSE per
`specs/001-doc-assistant-rag/contracts/openapi.yaml`.

---

## 2. Auth posture for browser-originated requests

**Decision**: Backend accepts unauthenticated requests **iff** the
`Origin` (or, when absent, `Referer`) header matches the host the
backend itself is serving (i.e., the static SPA was loaded from the same
origin as the API). For any other caller — missing `Origin`/`Referer`, or
a mismatched value — the existing `APP_SHARED_TOKEN` bearer requirement
stands unchanged. SPA bundle never reads, stores, or sends the token.

**Rationale**:

- Spec clarification Q2 (Session 2026-05-17): "No FE-side auth handling.
  Backend trusts same-origin requests from the served SPA." FR-024 +
  FR-025 forbid the token being baked into or read by the bundle.
- The check is deterministic (header presence + string match against the
  request's own URL host) and adds ~5 lines to the existing FastAPI
  bearer dependency. It does not require new infra.
- Non-browser callers (curl, future agents, CI) still authenticate with
  the bearer token — single-tenant trust model is preserved.
- A future production deploy with a reverse proxy injecting the bearer
  header continues to work: proxy adds `Authorization: Bearer …`, the
  same-origin path is irrelevant, no FE change.

**Alternatives considered**:

- *Token in `sessionStorage`* (Q2 Option B): rejected — exposes token to
  any XSS, and the spec already mandates safe escape of model output
  (FR-017). Defense-in-depth wins: zero token in browser memory at all.
- *Token in build-time env (`VITE_TOKEN`)*: rejected — directly violates
  FR-024.
- *Disable auth entirely when same-origin*: rejected — would let any
  browser anywhere reach the API if `Origin` is omitted; the header
  match closes that.
- *Add a per-session JWT minted on `/upload`*: rejected — invents
  infrastructure for a demo-grade single-tenant trust model.

**ADR**: `docs/adr/0007-spa-same-origin-auth.md` to be authored as part
of T0xx (see tasks.md). Captures threat model: in scope = "browser of a
trusted operator on a laptop"; out of scope = multi-tenant deployment
(re-evaluation triggered if multi-tenant becomes a requirement).

**Backend change required**: extend the existing bearer dependency in
`src/api/deps.py` with a same-origin bypass. Add a unit test that asserts
(a) request with matching `Origin` + no bearer = 200, (b) request with
mismatched `Origin` + no bearer = 401, (c) request with no `Origin` +
no bearer = 401, (d) request with bearer = 200 regardless of `Origin`.

---

## 3. Session handle persistence + rehydration

**Decision**: Store the active `session_id` in
`sessionStorage.setItem("doc-assistant.session", id)` immediately after a
successful `/upload`. On `App` mount, read it once; if present, call
`GET /history/{session_id}` to rehydrate the transcript. On 404 / 5xx /
network error, clear the key and render the empty upload state. On
`POST /session/end` (or "New Session" action), clear the key after the
backend call resolves (success **or** failure — see FR-018).

**Rationale**:

- Spec clarification Q4: per-tab persistence matches the "session is
  in-memory on the server" mental model. `localStorage` would survive
  the backend losing the session, leaving a stale handle.
- `GET /history/{session_id}` already exists (feature 001 commit
  `49d69f2`), so rehydration is a single round-trip with no new contract.
- In-flight streams are explicitly not resumed (spec edge-case bullet) —
  the SPA does not persist mid-stream state, only the handle.

**Alternatives considered**:

- *`localStorage`*: rejected (stale-handle risk after backend restart).
- *URL query string*: rejected (handle would leak into browser history,
  referer headers, and any pasted screenshots; spec wants the handle
  treated as a credential-adjacent secret).
- *No persistence*: rejected (every accidental refresh would lose the
  uploaded document, which dominates the demo cost).

---

## 4. Tailwind setup + component conventions

**Decision**: Tailwind CSS 4 via the `@tailwindcss/vite` plugin
(registered in `vite.config.ts`). **No `tailwind.config.{js,ts}`** and
**no `postcss.config.*`** — Tailwind 4 ships CSS-first config: a single
`frontend/src/styles/tailwind.css` entrypoint contains
`@import "tailwindcss";` plus a `@theme { ... }` block for design tokens
(colors, spacing, font stack). Content/source discovery is automatic in
v4; no content-globs to maintain. No `@layer components` global helpers
(keep utilities co-located). `clsx` for conditional class merging
(no `tailwind-merge` until duplication appears in practice).

**Rationale**:

- FR-020 forbids alternative styling. Tailwind utilities at component
  level are the only allowed mechanism.
- Tailwind 4's CSS-first config + auto source detection removes two
  config files (`tailwind.config.ts`, `postcss.config.cjs`) the v3
  approach required. Fewer config surfaces = fewer drift points.
- The official `@tailwindcss/vite` plugin replaces the v3 PostCSS step
  and is faster (Lightning CSS engine under the hood).
- `clsx` is < 1 KB and used by ~every React+Tailwind codebase; rejecting
  it would force ad-hoc string concatenation that ruins readability.
- A component layer of pre-baked helpers (`@layer components { .btn …}`)
  defeats the audit value of utilities being readable inline — explicit
  caveats noted in spec assumptions about minimal aesthetic.

**Alternatives considered**:

- *Tailwind 3 with JIT + `tailwind.config.ts`*: rejected — older config
  surface, slower build, no Lightning CSS. v4 is GA and stable.
- *`@tailwindcss/postcss` plugin instead of the Vite plugin*: rejected
  — the Vite plugin is the recommended path for Vite projects and
  avoids a stray `postcss.config.*` file.

**Alternatives considered**:

- *Headless UI / Radix*: rejected for this release — primitives like
  Dialog/Combobox aren't required by any user story; can be added later
  if accessibility audits surface a need (FR-016 baseline covered with
  semantic HTML + `aria-live` for the streaming announcement).
- *shadcn/ui*: rejected — pulls a CLI + copy-pasted components into
  source, harder to audit; spec doesn't ask for a component library
  surface, just primitives.

---

## 5. SPA state machine

**Decision**: A single `useReducer` for session+transcript with the
following discriminated union state:

```ts
type SessionState =
  | { kind: "empty" }
  | { kind: "uploading"; progress?: number }
  | { kind: "ready"; sessionId: string; transcript: Turn[] }
  | { kind: "streaming"; sessionId: string; transcript: Turn[]; controller: AbortController }
  | { kind: "error"; message: string; previous?: SessionState };
```

Transitions are explicit (`uploaded`, `submitQuestion`, `tokenAppended`,
`citationsReceived`, `streamDone`, `streamCancelled`, `streamErrored`,
`newSession`). All side effects (fetch, abort, sessionStorage writes)
happen in thin async action creators that dispatch synchronously.

**Rationale**:

- Spec FR-002 (four document states) + FR-012 (composer disabled while
  streaming) demand an enumerable state machine; a flag-based design
  (`isUploading`, `isStreaming`, `hasError`) leaks impossible combinations
  (`uploading && streaming`) that will eventually break.
- The reducer is testable in isolation (Vitest) without rendering
  components — direct compliance with Principle II.
- `AbortController` is owned by the streaming state, not stored on a ref
  outside React, so cancel-on-unmount is just `state.controller.abort()`.

**Alternatives considered**:

- *Zustand / Redux Toolkit*: rejected — single-screen app, no
  cross-tree subscriptions needed, and they pull external concepts
  reviewers shouldn't have to learn for a demo.
- *XState*: rejected — actor model is overkill; the union above is
  already a hand-written FSM.
- *Multiple booleans*: rejected (see above; spec demands explicit states).

---

## 6. Accessibility approach (FR-016 + SC-006)

**Decision**:

- Semantic HTML: `<main>`, `<form>` for composer, `<ul>` for transcript,
  `<button type="button">` for cancel/new-session.
- `aria-live="polite"` on the streaming turn container; switch to
  `aria-live="assertive"` for inline error messages.
- Visible focus rings via Tailwind `focus-visible:ring-2`.
- All controls keyboard-reachable: Enter submits composer; Esc cancels
  in-flight stream; `Ctrl/Cmd+K` opens new-session confirmation.
- Status is never conveyed by color alone (icons + text per state).

**Rationale**: directly maps each FR-016 sub-clause to a concrete
implementation. SC-006 keyboard walkthrough becomes a Playwright test
script: upload → send → cancel → copy → new-session, no mouse.

**Alternatives considered**:

- *Use a heavy ARIA toolkit*: rejected — base requirements are met with
  plain HTML + a few `aria-*` attributes; toolkit adds bundle cost.

---

## 7. Build + Docker integration

**Decision**: Extend the existing root `Dockerfile`'s `frontend-builder`
stage with `npm ci && npm run build`, outputting to
`/frontend/dist`. The final runtime stage copies that directory to
`/app/frontend_dist` and FastAPI mounts it via
`app.mount("/", StaticFiles(directory="/app/frontend_dist", html=True), name="spa")`
**after** all API routes (so `/upload`, `/ask`, etc. take precedence).

**Rationale**:

- FR-022 mandates a single image and `docker compose up` as the only
  start path. Build inside the image preserves reproducibility.
- `html=True` makes the SPA's client-side routes fall through to
  `index.html` for any non-API path — required for any future route
  beyond `/`.

**Alternatives considered**:

- *Separate FE container behind nginx*: rejected (FR-022 forbids a
  separate production FE service).
- *Build on host, copy artifacts in*: rejected (breaks reproducibility,
  forces Node on every reviewer's machine).

---

## 8. Testing strategy

**Decision**:

- **Unit (Vitest 4 + RTL, JSDOM)**: reducer state-machine, SSE parser
  wiring (feed it canned chunks, assert the right events), persistence
  read/write, UploadSurface render states, Composer disable rules
  (FR-012), keyboard-only flow assertions for SC-006 (RTL `userEvent`
  drives tab order, Enter to submit, Esc to cancel).
- **Contract (MSW 2)**: each `frontend/src/api/*.ts` exercised against
  MSW handlers built from the OpenAPI schema. Generated TS types via
  `openapi-typescript` 7.
- **Streaming integration (Vitest 4 + MSW 2)**: a dedicated test drives
  `api/ask.ts` against an MSW streaming `Response` that enqueues SSE
  frames with awaits between them. Asserts ≥ 2 `tokenAppended`
  dispatches arrive before `streamDone`, satisfying the constitution's
  streaming gate on the consumer side. Cancel path is asserted in the
  same file: `AbortController.abort()` mid-stream MUST result in a
  trailing turn marked `stopped`.
- **No headless browser, no Playwright, no Cypress.** Rationale and
  the MSW-streaming mechanism are detailed in §11.

**Rationale**: matches Principle II's "streaming endpoint MUST have a
test that asserts response is incremental" — now enforced on the
**consumer** side too, without a browser. Constitution requires the
existing backend SSE test to stay; this adds the symmetric FE
assertion using only Vitest + MSW.

**Alternatives considered**:

- *Playwright / Cypress*: rejected — explicitly dropped (see §11);
  incrementality is a parser/reducer concern, not a browser concern.
- *Skip the streaming integration test, rely on backend's test alone*:
  rejected — see §11 final bullet; the SPA could regress to a buffer-
  then-render shape without it.

---

## 9. Bundle size guardrail

**Decision**: CI step runs `npm run build` and fails if the
production gzipped bundle exceeds 300 KB total (200 KB JS + 100 KB CSS).
Measured by `vite-plugin-bundle-visualizer` output checked against a
threshold script.

**Rationale**: Performance Goals declare the cap. A regression check
makes the cap enforceable in code review (Principle IV: numbers, not
adjectives).

**Alternatives considered**:

- *No cap*: rejected — Tailwind without purge or a misconfigured import
  blows the cap silently.
- *Pixel-perfect cap*: rejected — too brittle; 300 KB gzipped is a
  generous, defensible ceiling.

---

---

## 10. Dependency versions (latest stable, 2026-05-17)

**Decision**: Pin to the latest stable major of every marquee package.
Floor versions:

| Package | Floor | Notes |
|---------|-------|-------|
| `react`, `react-dom` | 19.x | New `use()` hook + Actions API available; we still rely on `useReducer` for the FSM. |
| `typescript` | 6.0.x (6.0.3 floor) | Final JS-codebase release per Microsoft; TS 7 still beta (Go-native rewrite). Strict mode, `verbatimModuleSyntax`. |
| `vite` | 8.x | Rolldown-backed dev/build, Lightning CSS in default pipeline. |
| `@vitejs/plugin-react` | latest matching Vite 8 | |
| `tailwindcss` | 4.x | CSS-first config (`@theme`), auto source detection. |
| `@tailwindcss/vite` | 4.x | Replaces v3 PostCSS step. |
| `clsx` | 2.x | |
| `eventsource-parser` | 3.x | ESM-only; works under Vite 8 native ESM. |
| `vitest` | 4.x (4.1.6 floor) | Latest stable line; native Vite 8 integration. v5 in beta — not adopted. |
| `@testing-library/react` | React 19-compatible release | |
| `@testing-library/jest-dom` | latest | |
| `msw` | 2.x | Native `fetch` interception + streaming responses (used for the SSE incrementality test in place of Playwright). |
| `openapi-typescript` | 7.x | Generates discriminated unions from the v3.1 schema. |
| `eslint` | 9.x flat-config | `typescript-eslint` 8.x. |
| `prettier` | 3.x | |

**Rationale**:

- React 19 is GA and the constitution does not pin React. The Actions
  API is incidental; we use it only inside `Composer` for the
  optimistic user-turn append.
- TypeScript 6.0.3 is the latest stable (TS 7 beta exists but is the
  in-progress Go-native rewrite — not adopted until GA).
- Vite 8 + Vitest 4 is the supported pairing at this date; Vitest 5
  is still beta and not adopted.
- Tailwind 4's CSS-first approach has been GA for several months; the
  Vite 8 docs explicitly list `@tailwindcss/vite` as the recommended
  integration.
- MSW 2 intercepts at the `fetch` level **and** supports streaming
  `Response` bodies, which is exactly the transport the SPA uses
  (`fetch` + `ReadableStream`). This is why MSW can replace a headless
  browser for the incrementality assertion — see §11 below.
- `openapi-typescript` 7 outputs proper discriminated unions for our
  `Error` enum codes; v6 collapsed them to `string`.

**Alternatives considered**:

- *Stay on React 18 / Vite 5 / TS 5.x*: rejected — user explicitly
  asked for the latest of each; downstream tooling (Vitest 4, RTL,
  Tailwind 4 plugin) all have matching releases, so there is no
  compat hold.
- *Adopt TS 7 beta / Vitest 5 beta*: rejected — pre-release on a demo
  project is unjustified risk; revisit after GA.
- *Use Bun or Deno as the SPA toolchain*: rejected — out of scope and
  not on the constitution's locked stack list.

**Verification step (T0xx)**: a `npm ci && npx tsc --noEmit && npm run
build && npm test -- --run` clean run inside the `frontend-dev`
container with the pinned versions is a precondition for merging the
scaffold task.

---

## 11. SSE-incrementality assertion without a headless browser

**Decision**: Drop Playwright. Replace the consumer-side
streaming-incrementality test with a Vitest 4 test under JSDOM that
exercises the real `api/ask.ts` against an MSW 2 streaming handler.
The handler returns a `Response(new ReadableStream({ start(ctrl) { … } }))`
that enqueues SSE frames with deliberate `await new Promise(r =>
setTimeout(r, 10))` waits between them. The test asserts that the
reducer received ≥ 2 distinct `tokenAppended` dispatches **before** the
`streamDone` dispatch, with the gap between dispatches > 0 ms.

**Rationale**:

- The constitution's streaming gate (Principle II) says "MUST assert
  the response is incremental (multiple chunks observed) and not
  buffered to completion." It does not require a browser. The backend
  already owns the HTTP-layer streaming test; the SPA's contribution
  is asserting the *consumer parses incrementally*, which is a pure
  client-side concern testable with a streaming `Response`.
- Removes a heavy dependency (Playwright + Chromium download in CI
  ≈ 250 MB), removes a separate test runner, and keeps the FE test
  suite in one Vitest invocation.
- MSW 2's streaming `Response` is the same primitive `/ask` produces
  on the wire, so the test exercises the parser, the reducer, and the
  cancel path against the real client code with realistic timing.

**Alternatives considered**:

- *Keep Playwright Chromium*: rejected — user asked to drop it, and
  the incrementality guarantee is achievable without it.
- *Hit the real backend from Vitest via `fetch`*: rejected — would
  require spinning the FastAPI process inside the FE container,
  coupling SPA tests to a working LLM provider / network. Backend
  already owns that test.
- *Skip the consumer-side test, rely on backend's streaming test
  alone*: rejected — would let the SPA regress into "buffer the whole
  stream, render once" without anyone noticing until manual demo.

---

## Resolved NEEDS CLARIFICATION

None remain. All five spec-level clarifications (Session 2026-05-17) plus
the technical-context items above are settled. Ready for Phase 1.
