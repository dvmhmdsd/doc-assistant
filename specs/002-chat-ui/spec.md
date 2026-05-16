# Feature Specification: Chat UI (Upload + Streaming Q&A)

**Feature Branch**: `002-chat-ui`

**Created**: 2026-05-15

**Status**: Draft

**Input**: User description: "we need to also develop a nice UI for upload and for questions and streaming (chat interface)"

## Clarifications

### Session 2026-05-15

- Q: Client tech stack? → A: React + Tailwind CSS (locked at the spec level; rationale captured in a dedicated ADR).
- Q: How is the frontend containerized? → A: Production = multi-stage root Dockerfile builds the SPA into static assets served by the backend container at the same origin (no separate production FE service). Dev = optional `frontend-dev` service via the `dev` compose profile (Vite hot-reload, port 5173, proxies to backend). `docker compose up` is the only supported start path.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Upload a document from the UI (Priority: P1)

A reviewer opens the assistant in a browser. A clear upload area greets them. They drag a PDF onto it (or click to pick a file), watch a progress indicator while it ingests, and see a confirmation that the document is ready to be queried.

**Why this priority**: Without an upload surface, no one can use the assistant. This is the entry point to every other interaction.

**Independent Test**: Open the app in a fresh browser tab, drag a PDF onto the upload area, confirm a visible progress state during ingestion and an explicit "ready" confirmation when ingestion completes.

**Acceptance Scenarios**:

1. **Given** the user lands on the chat UI for the first time, **When** they see the upload surface, **Then** the next action (drop or pick a file) is unambiguous without reading documentation.
2. **Given** the user drops a supported file, **When** ingestion begins, **Then** a determinate-or-indeterminate progress indicator is shown until "ready" appears.
3. **Given** the user picks an unsupported file or one over the size cap, **When** the upload is attempted, **Then** the UI rejects it inline with a specific reason and does not lock the rest of the interface.
4. **Given** an upload is in progress, **When** the user tries to ask a question, **Then** the UI clearly indicates the document is not yet ready and prevents premature submission.

---

### User Story 2 - Ask a question and watch the answer stream (Priority: P1)

After ingestion, the user types a question into a chat composer and presses send. Their question appears immediately in the transcript. The assistant's answer renders progressively token-by-token. The user can read earlier text while later text is still arriving. Once the answer ends, the composer is ready for the next question.

**Why this priority**: Streaming Q&A is the core value proposition. A non-streaming or laggy answer destroys perceived responsiveness.

**Independent Test**: After uploading a document, type a question, press send, observe (a) the question appears immediately in the transcript, (b) answer text starts appearing within ~2 seconds, (c) text continues to grow visibly without layout jank, (d) composer is re-enabled when the answer finishes.

**Acceptance Scenarios**:

1. **Given** a ready document, **When** the user submits a question, **Then** their question appears immediately as a user-attributed message in the transcript.
2. **Given** a question is in flight, **When** the assistant begins responding, **Then** answer text appears progressively (not as a single delayed block) and the assistant message is clearly attributed.
3. **Given** an answer is streaming, **When** the user scrolls up to read earlier turns, **Then** the auto-scroll does not yank them back to the bottom; an explicit "jump to latest" affordance appears.
4. **Given** an answer is streaming, **When** the user clicks a stop/cancel control, **Then** streaming halts cleanly and the partial answer is preserved in the transcript with a clear "stopped" marker.

---

### User Story 3 - Continue a multi-turn conversation (Priority: P2)

The user keeps asking follow-up questions. Each turn appears in order in the transcript. Pronouns and references in follow-ups resolve correctly because the prior turns are visible (and used by the assistant). The transcript stays readable as it grows.

**Why this priority**: Single-question UX is useful; multi-turn UX is what makes the product feel like an assistant. P2 because Story 1 + Story 2 already deliver value alone.

**Independent Test**: After receiving one answer, send a pronoun-bearing follow-up; confirm the new exchange is appended in order and the answer reflects prior context.

**Acceptance Scenarios**:

1. **Given** the transcript has prior turns, **When** the user submits a follow-up, **Then** the new turn is appended at the bottom with consistent styling and clear role attribution.
2. **Given** a long transcript, **When** the user scrolls, **Then** turns remain readable (clear separation between user and assistant messages, no overlap, no clipping).

---

### User Story 4 - Recover gracefully from errors (Priority: P2)

Things go wrong: the upload fails partway, the network drops mid-stream, the AI provider returns an error. The user sees a clear, human-readable message in the chat surface itself — not a popup, not a raw stack trace — and can retry without losing prior context.

**Why this priority**: Errors are inevitable. A demo that silently fails or shows a 500 page is worse than a slow one.

**Independent Test**: Simulate a mid-stream error (kill the connection or use an invalid provider key) and confirm the UI shows a recoverable error message with a retry affordance and preserved history.

**Acceptance Scenarios**:

1. **Given** an upload fails, **When** the failure is detected, **Then** the upload area returns to its idle state with an inline error explaining what to do next.
2. **Given** an answer is streaming and the connection drops, **When** the failure is detected, **Then** the partial answer is marked as interrupted, the transcript is preserved, and a retry control is offered.
3. **Given** any error message, **When** it is shown to the user, **Then** it MUST NOT contain raw stack traces, internal identifiers, or provider credentials.

---

### User Story 5 - Use the assistant on a small screen (Priority: P3)

The user opens the chat UI on a narrow viewport (laptop split-screen, tablet, or large phone). The upload area, transcript, and composer all remain usable: nothing is hidden behind horizontal scroll, the composer remains anchored, the transcript stays scrollable.

**Why this priority**: Reviewers often have multiple windows side by side. Useful, not blocking.

**Independent Test**: Resize the browser to ~600 px wide; confirm upload, sending a question, and reading a streamed answer all work without horizontal scroll and without the composer disappearing.

**Acceptance Scenarios**:

1. **Given** a viewport ≤ 768 px wide, **When** the user uses upload, composer, and transcript, **Then** all controls remain reachable without horizontal scrolling.
2. **Given** a long answer is streaming on a narrow viewport, **When** the user types in the composer, **Then** the composer remains visible and not obscured by the streaming text.

---

### Edge Cases

- User submits an empty question or whitespace-only input → composer rejects it without sending; no transcript pollution.
- User pastes a very long question (thousands of characters) → composer either accepts it or shows a clear character/length limit; submission does not silently truncate.
- User sends a second question while the previous answer is still streaming → either the new question is queued (with a clear "waiting" indicator) or the composer is disabled until the prior stream finishes; behavior is consistent and predictable.
- Upload of a 25 MB file on a slow connection → progress indicator must keep advancing or show a stalled-state warning; user can cancel.
- Rapid double-click on send → exactly one question is submitted; no duplicates in transcript.
- Browser refresh mid-session → user is informed prior in-memory history is lost (or it gracefully re-bootstraps if a session handle is recoverable); no silent partial state.
- Copy/paste an assistant answer → copying yields plain text that matches what was rendered (no hidden markup leaks).
- Very fast streaming (many tokens/sec) → text reflows without flicker or visible jank; CPU does not pin.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: UI MUST present a single, immediately-visible upload surface on first load that supports both drag-and-drop and click-to-pick.
- **FR-002**: UI MUST visibly distinguish four document states: empty (no file), uploading/processing, ready, and error. Transitions between states MUST be visible to the user.
- **FR-003**: UI MUST display a progress indicator during upload and ingestion; if duration cannot be predicted, an indeterminate indicator is acceptable.
- **FR-004**: UI MUST reject unsupported file types and oversized files client-side before submission where the file type/size is determinable in the browser, and MUST also surface server-side rejection messages inline.
- **FR-005**: UI MUST prevent question submission until at least one document is in the "ready" state and MUST communicate this prerequisite to the user.
- **FR-006**: UI MUST render a chat transcript with clear role attribution (user vs. assistant) and chronological ordering of turns.
- **FR-007**: UI MUST append the user's question to the transcript synchronously on submit (before any network response).
- **FR-008**: UI MUST render assistant answers progressively as tokens arrive (no waiting for the full response).
- **FR-009**: UI MUST display the first visible answer token within 2 seconds of submission in 95% of attempts under normal load.
- **FR-010**: UI MUST provide a control to stop/cancel an in-progress answer; cancellation MUST preserve the partial answer in the transcript with a visible "stopped" marker.
- **FR-011**: UI MUST auto-scroll the transcript to the latest token by default, but MUST NOT yank the view back to the bottom if the user has manually scrolled up; an explicit "jump to latest" affordance MUST appear in that case.
- **FR-012**: UI MUST disable or queue the composer in a documented, consistent way while a prior answer is streaming, with a visible indicator of the current state.
- **FR-013**: UI MUST surface all errors (upload, ingestion, question, stream) inline in the chat surface as human-readable messages and MUST NOT expose raw stack traces, provider IDs, or credentials.
- **FR-014**: UI MUST provide a retry affordance for any failed operation (upload, question, interrupted stream) that does not require the user to re-enter the entire flow.
- **FR-015**: UI MUST remain usable on viewports as narrow as 600 px without horizontal scrolling and without the composer becoming hidden.
- **FR-016**: UI MUST meet basic accessibility expectations: every interactive control has a keyboard equivalent, focus state is visible, color is not the sole signal of state, and screen-reader announcements occur for state changes (e.g., "answering", "answer complete", "error").
- **FR-017**: UI MUST treat the user's input as text-only and MUST escape/render assistant output safely (no execution of HTML/script injected via document content or model output).
- **FR-018**: UI MUST allow the user to start a fresh session/conversation in one obvious action, clearing the transcript and prompting for a new upload.
- **FR-019**: UI MUST allow the user to copy any single assistant message to the clipboard with a one-click action.
- **FR-020**: UI MUST be implemented as a React single-page application styled with Tailwind CSS. No alternative client framework (Vue, Svelte, Angular, vanilla DOM, jQuery) is permitted. No alternative styling system (CSS-in-JS, Bootstrap, raw global CSS beyond Tailwind's base layer, ad-hoc inline styles for layout) is permitted; component-level utility classes via Tailwind are the styling mechanism.
- **FR-021**: Project MUST include a dedicated Architecture Decision Record covering the choice of React + Tailwind for the chat client. The ADR MUST state context, the decision, alternatives considered (at minimum: vanilla HTML/JS as suggested by KICKOFF, plus one server-rendered alternative such as HTMX), and consequences (bundle size, build complexity, hiring/familiarity, accessibility implications, RTL/i18n posture). This ADR is in addition to the five ADRs required by the upstream feature.
- **FR-022**: Frontend MUST be containerized. The production build MUST be performed inside a multi-stage Docker build at the repository root and the resulting static assets MUST be served by the backend container on the same origin (no separate frontend service in the production compose profile). `docker compose up` MUST be the only documented start path; running `npm run dev` directly on the host MUST NOT appear in the README or quickstart as a supported start path.
- **FR-023**: A dedicated frontend development container MUST exist (`frontend/Dockerfile.dev`) and be wired into `docker-compose.yml` under a `dev` profile, providing Vite hot-reload (port 5173) that proxies API calls to the backend service over the compose network. The dev container MUST NOT be required to ship the product — it exists only to give developers a hot-reload loop without installing Node on the host.
- **FR-024**: The frontend container image MUST NOT include any backend secrets at build time. `APP_SHARED_TOKEN` and any provider API keys MUST be supplied to the running backend container via the `.env`/env-file mechanism only and MUST NOT be baked into the FE image, the FE bundle, or any HTML the FE serves.

### Key Entities

- **Upload Surface**: The region that accepts a file and conveys document state (empty / uploading / ready / error).
- **Transcript**: The ordered, scrollable list of turns in the current session.
- **Turn**: A single message in the transcript, attributed to either the user or the assistant, with a state (sent / streaming / complete / stopped / errored).
- **Composer**: The text input + send/cancel controls used to author a new question.
- **Session Indicator**: Visible signal of the current session (and the document attached to it), plus a control to start a new session.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new user can complete their first end-to-end interaction (upload → ask → see streamed answer) in under 60 seconds on first use, without external documentation.
- **SC-002**: First visible answer token reaches the user within 2 seconds of submission in 95% of attempts under normal load.
- **SC-003**: On a usability test with 5 new users, at least 4 of 5 can identify "where to upload" and "how to send a question" within 5 seconds of opening the app, with no prompting.
- **SC-004**: Streaming a 500-word answer causes no visible UI freezes (input remains responsive throughout) and finishes rendering in proportion to token arrival.
- **SC-005**: Every error condition surfaced during testing (bad file type, oversize file, mid-stream disconnect, provider failure) is rendered as a human-readable message inline; zero raw stack traces or credentials are exposed in the UI in 100% of cases.
- **SC-006**: The UI passes a keyboard-only walkthrough: upload, send, cancel, copy, and start-new-session can all be performed without a pointing device.
- **SC-007**: Reflowing the viewport from 1440 px to 600 px wide leaves all primary controls reachable with no horizontal scrollbar and no obscured composer.
- **SC-008**: On a usability test, at least 4 of 5 users describe the assistant as "responsive" or equivalent positive language, citing the streaming behavior.

## Assumptions

- The UI is a browser-based, single-page surface served by the same backend as the underlying assistant. Native mobile, desktop installers, and embeddable widgets are out of scope for this release.
- One document per session is the supported flow for the initial release (matches the upstream spec). Multi-document selection in the transcript is a future extension.
- Conversation history is in-memory for the lifetime of the server process (matches the upstream spec). On browser refresh, prior history is lost unless a server-known session handle is preserved client-side.
- Visual styling targets a clean, modern, minimal aesthetic — readable typography, neutral palette, high contrast — over heavy branding. Visual design (final palette, spacing scale, exact component variants) is delegated to implementation; this spec governs structure, behavior, and the client tech stack.
- Client tech stack is locked: React (with TypeScript) for the SPA, Tailwind CSS for styling. The choice supersedes the "minimal HTML/JS" suggestion in KICKOFF.md and is itself a tradeoff (heavier bundle, build pipeline) that MUST be documented in a dedicated ADR.
- Containerization is locked: the production runtime is a single image (the SPA is built inside the root `Dockerfile`'s `frontend-builder` stage and copied into the FastAPI runtime stage). A separate `frontend-dev` service exists in `docker-compose.yml` under the `dev` profile for hot-reload; it is not a production deliverable. `docker compose up` is the only supported start path (no host-side `npm run dev` or `uvicorn` instructions in the README).
- The composer accepts plain text only. Rich text, file attachments inside the composer, and voice input are out of scope for this release.
- Internationalization (right-to-left layouts, translations) is out of scope for this release. UI strings are in English.
- The UI cooperates with the same upload size cap (25 MB) and supported file types (PDF, DOCX) defined by the upstream feature.
