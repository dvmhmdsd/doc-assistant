# Feature Specification: Doc Assistant (RAG-Powered Document Q&A)

**Feature Branch**: `001-doc-assistant-rag`

**Created**: 2026-05-15

**Status**: Draft

**Input**: User description: "we need to build a doc assistant app that follows the plan in @KICKOFF.md which exposes the upload, also accepts the question query and streams the response back. The upload should be efficient and fast, we should follow strictly the principles and the design in the kickoff file. We need to plan for ADRs for why we chose the current architecture and why we chose specific tools instead of other options and explain the tradeoffs, use the adr-writer agent for this."

## Clarifications

### Session 2026-05-15

- Q: How should the app gate access in v1? → A: Single shared secret (env-set token) required for every API call.
- Q: Does v1 support concurrent isolated sessions? → A: Multiple concurrent sessions, each isolated by session handle (no cross-session document or history access).
- Q: When must a session's indexed chunks and history be purged? → A: On explicit "end session" action OR after a configurable idle TTL (default 24h), whichever comes first.
- Q: How aggressively must the server auto-retry failing LLM/embedding calls? → A: Bounded retry — up to 2 retries on transient errors (5xx, network, timeout) with exponential backoff, total budget ≤ 5 s; then surface the error.
- Q: What operational telemetry is required in v1? → A: Structured logs + per-request timing metrics (ingest duration, retrieval latency, time-to-first-token, total stream duration) exposed at a local endpoint; no external tracing collector; secrets never logged.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Upload a document and get an answer (Priority: P1)

A reviewer at a legal-tech firm needs to interrogate a single agreement quickly. They open the assistant, upload one PDF or Word file, type a plain-language question (e.g. "What is the termination notice period?"), and watch the answer appear progressively in the chat window — without waiting for the full response to finish before seeing anything.

**Why this priority**: Minimum viable slice. Without upload + first streamed answer, nothing else in the product has value.

**Independent Test**: Upload a sample contract, ask one question, observe a partial answer rendered within seconds and grounded in the document's text.

**Acceptance Scenarios**:

1. **Given** a supported PDF under the size cap, **When** the user uploads it, **Then** the system confirms ingestion within the documented time budget and returns a stable document handle the user can reference.
2. **Given** an uploaded document, **When** the user asks a question whose answer is present in the document, **Then** the first words of the answer appear within 2 seconds and the full answer reflects the document's content.
3. **Given** an uploaded document, **When** the user asks a question whose answer is NOT in the document, **Then** the system explicitly says it could not find the information rather than fabricating one.

---

### User Story 2 - Ask follow-up questions in the same conversation (Priority: P2)

The reviewer asks a clarifying follow-up that depends on earlier turns ("and what about the renewal clause?"). The assistant remembers prior context within the same session and answers without requiring the user to repeat the document name or earlier question.

**Why this priority**: Single-shot Q&A is fine; multi-turn Q&A is what makes it feel like an assistant.

**Independent Test**: After completing User Story 1, send a pronoun-bearing follow-up ("how long is that?") and confirm the answer correctly resolves to the entity from the previous turn.

**Acceptance Scenarios**:

1. **Given** an active session with at least one prior question, **When** the user asks a follow-up that references prior context, **Then** the answer reflects that context.
2. **Given** an active session, **When** the user fetches conversation history, **Then** they receive the full ordered list of user/assistant turns for that session.

---

### User Story 3 - Operator swaps the AI provider without code changes (Priority: P3)

An operator running the assistant needs to switch between providers (for cost, latency, or availability reasons) by editing configuration only — no code edits, no rebuilds beyond restarting the app.

**Why this priority**: Required by the project's portability goal; protects against single-provider risk.

**Independent Test**: Change the provider setting in configuration, restart, repeat Story 1, and confirm identical user-visible behavior.

**Acceptance Scenarios**:

1. **Given** the system is configured with provider A, **When** the operator changes the provider setting to provider B and restarts, **Then** uploads and questions continue to work with no source code changes.
2. **Given** a switch to a different embedding provider, **When** a new document is uploaded after the switch, **Then** it is ingested and answerable under the new provider without manual intervention.

---

### User Story 4 - Architecture decisions are recorded for reviewers (Priority: P3)

A reviewer (engineering lead, auditor, future maintainer) needs to understand *why* the system is built the way it is. They open a small set of decision records and find a concise explanation for each major choice (architecture style, vector store, parser choices, AI/embedding provider strategy, streaming approach, client tech stack) including alternatives considered and tradeoffs accepted.

**Why this priority**: Required by the project brief. Without ADRs, the codebase is hard to evaluate and hard to evolve.

**Independent Test**: Open the ADR folder and confirm each major decision listed below has a record with Context / Decision / Alternatives / Consequences.

**Acceptance Scenarios**:

1. **Given** the published project, **When** a reviewer browses the decision records, **Then** each ADR follows a consistent structure and clearly states the tradeoffs.
2. **Given** a major design choice exists in the code, **When** the reviewer searches the ADR index, **Then** a corresponding record exists (no major unexplained decisions).

---

### Edge Cases

- File exceeds the size cap → upload is rejected with a clear, human-readable message before any parsing begins; no partial state is persisted.
- Unsupported file type (e.g. image, plain text, password-protected PDF) → upload is rejected with a specific reason, not a generic failure.
- Document parses to empty or near-empty text (e.g. scan-only PDF with no OCR layer) → user is told the file is not extractable rather than receiving "no relevant content" on every question.
- Question is asked against an unknown or expired document handle → returns a clear error, not a fabricated answer.
- AI provider is unreachable or returns a transient error → server auto-retries up to 2 times with exponential backoff within a 5 s total budget; if still failing, user sees a recoverable error in the chat surface and session/history are preserved so the user can retry manually. Non-transient errors (4xx other than 429) MUST be surfaced immediately without retry.
- Two questions sent in rapid succession on the same session → both are answered in order; history reflects both turns.
- Document contains no information relevant to the question → assistant explicitly says so rather than hallucinating.
- Very long answer → streaming continues without UI freeze; user can read earlier text while later text still arrives.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST accept uploads of PDF and Word (DOCX) documents and reject every other file type with a clear, user-facing reason.
- **FR-002**: System MUST return a stable document handle upon successful upload that the user can reference for subsequent questions in the same session.
- **FR-003**: System MUST enforce a documented upload size cap and reject oversized files before any parsing or storage occurs.
- **FR-004**: System MUST extract textual content from uploaded documents and prepare it for retrieval before answering any question against that document.
- **FR-005**: System MUST accept natural-language questions tied to a session and a previously uploaded document.
- **FR-006**: System MUST stream answer tokens to the user progressively, with the first visible token arriving within 2 seconds (p95) under normal load.
- **FR-007**: System MUST ground answers in the content of the uploaded document(s) and MUST explicitly state when the document does not contain the requested information rather than fabricating one.
- **FR-008**: System MUST retain conversation turns (user questions and assistant answers) for the lifetime of a session and MUST include prior turns when answering follow-up questions.
- **FR-009**: System MUST expose a way to fetch the ordered conversation history for a given session.
- **FR-010**: System MUST allow swapping the AI text-generation provider and the embedding provider via configuration only (no source code edits, no rebuild beyond restart).
- **FR-011**: System MUST surface upload and question errors as human-readable messages in the user interface and MUST NOT expose raw provider stack traces or secrets.
- **FR-012**: System MUST visibly indicate at least three states to the user: idle, uploading/processing, and answering/streaming.
- **FR-013**: System MUST be runnable end-to-end with a single bring-up command on a developer machine, with no separately managed external database service.
- **FR-014**: Project MUST include Architecture Decision Records that, at minimum, document: (a) the choice of a custom retrieval pipeline over an orchestration framework, (b) the choice of vector store, (c) the choice of PDF and DOCX parsers, (d) the strategy for swappable AI/embedding providers, (e) the choice of streaming approach, and (f) the choice of client tech stack (React + Tailwind, as required by feature 002-chat-ui). Each ADR MUST state context, decision, alternatives considered, and consequences.
- **FR-015**: System MUST treat API keys and other secrets as configuration values loaded from the environment; secrets MUST NOT be logged, echoed in error responses, or committed to the repository.
- **FR-016**: System MUST clean up temporary files created during upload after ingestion completes (or document its retention behavior explicitly).
- **FR-017**: System MUST require a shared access token, loaded from environment configuration, on every API request. Requests without the token (or with an incorrect token) MUST be rejected with an authentication error and MUST NOT trigger uploads, questions, or history reads. The token value MUST NOT be logged or echoed in error responses.
- **FR-018**: System MUST support multiple concurrent sessions. Each session MUST be isolated by its session handle: a question asked in session A MUST NOT retrieve chunks from documents uploaded in session B, and conversation history of one session MUST NOT be readable from another. Session handles MUST be unguessable (cryptographically random) so they cannot be enumerated.
- **FR-019**: System MUST purge a session's indexed chunks, vector entries, and conversation history when (a) the user explicitly ends the session, or (b) the session has been idle longer than a configurable TTL (default 24 hours), whichever occurs first. Purge MUST remove the data from the vector store and from any on-disk caches associated with the session. The TTL MUST be configurable via environment variable without code changes.
- **FR-020**: System MUST expose a way for the user (or UI) to explicitly end a session, after which that session's handle MUST NO LONGER grant access to any prior documents or history.
- **FR-021**: System MUST automatically retry transient AI provider failures (network errors, timeouts, HTTP 5xx, HTTP 429) up to 2 times using exponential backoff, with a total retry budget of 5 seconds per user-facing request. Non-transient failures (other 4xx) MUST be surfaced immediately without retry. After the retry budget is exhausted, the failure MUST be surfaced to the user as a recoverable error with a retry affordance, and the session MUST remain valid.
- **FR-022**: System MUST emit structured logs for every request (correlation/request ID, timestamp, level, event, session handle hash — never the raw handle, never secrets). Logs MUST NOT contain API keys, raw session handles, raw question/answer text, or document contents.
- **FR-023**: System MUST record and expose per-request timing metrics at a local metrics endpoint, including at minimum: ingest duration, retrieval latency, time-to-first-token, total stream duration, and provider retry count. These metrics MUST be sufficient to verify SC-001 and SC-002 from a single running instance without requiring an external tracing collector.

### Key Entities

- **Document**: A user-uploaded file (PDF or DOCX). Has a stable handle, an extracted textual representation, and an indexed retrievable form. Belongs implicitly to the session that uploaded it.
- **Chunk**: A retrievable slice of a document's text, sized to fit retrieval context. Carries enough surrounding context to be self-explanatory when surfaced to the AI.
- **Session**: A conversational thread identified by a session handle. Owns an ordered list of conversation turns and (transitively) the documents asked about within it.
- **Conversation Turn**: A single user question or assistant answer within a session, ordered chronologically.
- **Provider Configuration**: The named selection of AI generation provider and embedding provider currently in effect, plus their credentials. Changes require a restart but no code change.
- **Architecture Decision Record**: A standalone document describing one significant design choice (context, decision, alternatives, consequences).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can upload a 50-page document and receive a usable document handle in under 30 seconds on a typical laptop.
- **SC-002**: After a question is submitted, the first words of the answer become visible to the user within 2 seconds in 95% of attempts under normal load.
- **SC-003**: Follow-up questions that depend on prior context are answered correctly in at least 90% of attempts on a small evaluation set, without the user repeating earlier context.
- **SC-004**: When the document does not contain the answer, the assistant says so explicitly (instead of fabricating one) in at least 95% of evaluation cases.
- **SC-005**: An operator can switch between any two supported AI providers and any two supported embedding providers using configuration only, with the user-visible upload and Q&A flows continuing to pass acceptance scenarios after the switch.
- **SC-006**: A new user can go from "I have a document" to "I have a streamed answer" in under 60 seconds on first use, without reading documentation beyond the in-app UI.
- **SC-007**: A reviewer browsing the project's decision records can find one record per major design choice (architecture style, vector store, parsers, provider strategy, streaming approach, client tech stack), each with context / decision / alternatives / consequences clearly separated.
- **SC-008**: A developer can bring the entire system up locally with a single documented command and reach a working chat UI in under 5 minutes from a clean machine.

## Assumptions

- Primary user is an internal reviewer (e.g. legal-tech analyst). Public, anonymous internet exposure is out of scope for the initial release; basic single-user usage on a trusted machine or internal network is assumed. Access is gated by a single shared secret (env-set token) on every API call; per-user accounts and SSO are deferred.
- Default upload cap: 25 MB per file. One document per session is sufficient for the initial release; multi-document sessions are a future extension.
- Sessions are ephemeral and identified by an unguessable, cryptographically random session handle; persistent user accounts and authentication are out of scope for the initial release. Multiple concurrent sessions are supported and MUST be isolated from each other (no cross-session document or history access).
- Conversation history is retained per session until the session is explicitly ended OR has been idle longer than the configurable TTL (default 24 hours), whichever comes first. Durable persistence of conversations across server restarts is a future extension.
- Only PDF and DOCX are supported in the initial release. OCR for scan-only PDFs is out of scope (the system will report that no text could be extracted).
- System runs on a single developer-class machine; horizontal scale and multi-tenant isolation are out of scope for this release.
- ADRs are authored using the project's `adr-writer` agent and stored under a `docs/adr/` directory using a consistent, lightweight template.
- The retrieval pipeline is bespoke (deliberately not built on a higher-level orchestration framework) to keep the codebase auditable for reviewers; this is itself a tradeoff that will be recorded as an ADR.
