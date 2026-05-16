<!--
SYNC IMPACT REPORT
==================
Version change: (template, unversioned) -> 1.0.0
Bump rationale: Initial ratification of project constitution. No prior versioned constitution
existed; all placeholders replaced with concrete principles derived from KICKOFF.md.

Modified principles: N/A (initial adoption)
Added principles:
  - I. Code Quality & Clean Architecture (NON-NEGOTIABLE)
  - II. Test-First Discipline (NON-NEGOTIABLE)
  - III. User Experience Consistency
  - IV. Performance & Streaming Responsiveness
  - V. Configuration-Driven Extensibility

Added sections:
  - Additional Constraints (technology stack, security, dependencies)
  - Development Workflow & Quality Gates

Removed sections: None

Templates requiring updates:
  - .specify/templates/plan-template.md ............ ⚠ pending (Constitution Check
    section still contains placeholder "[Gates determined based on constitution file]";
    update on first /speckit.plan run to enumerate the five concrete gates below)
  - .specify/templates/spec-template.md ............ ✅ no change needed
    (technology-agnostic; aligns with current scope/requirements model)
  - .specify/templates/tasks-template.md ........... ✅ no change needed
    (TDD ordering + integration-test categories already match Principle II)
  - .specify/templates/checklist-template.md ....... ✅ no change needed
  - .specify/templates/constitution-template.md .... ✅ source template, untouched

Follow-up TODOs: None. RATIFICATION_DATE set to 2026-05-15 per initial adoption.
-->

# Doc Assistant Constitution

## Core Principles

### I. Code Quality & Clean Architecture (NON-NEGOTIABLE)

The codebase MUST stay readable, modular, and free of unnecessary framework lock-in. To that end:

- LangChain, LlamaIndex, and equivalent orchestration frameworks MUST NOT be introduced; the
  custom layered architecture in `src/` (parsers, chunker, embeddings, vector_store, llm,
  services, history, api) is the canonical structure.
- Every cross-layer dependency MUST go through an interface defined in the KICKOFF contracts
  (`DocumentParser`, `EmbeddingProvider`, `VectorStore`, `LLMClient`, `ConversationStore`).
  Concrete classes MUST be injected, never imported across layers directly.
- The Strategy, Factory, Repository, and Facade patterns identified in KICKOFF MUST be the
  default response to "where does this code go?". New patterns require written justification
  in the plan's Complexity Tracking table.
- Public functions and classes MUST have type hints. Modules MUST pass linting and static
  type checking before merge (ruff + mypy or pyright; failures block merge).
- No dead code, no commented-out blocks, no TODO without an owner and a linked issue.

**Rationale**: The project is explicitly designed to *demonstrate* OOP and design patterns;
hidden abstractions or framework magic defeat its purpose. Interfaces also enforce the
swap-LLM / swap-embedding success criterion from KICKOFF.

### II. Test-First Discipline (NON-NEGOTIABLE)

Tests MUST exist before the code they cover is merged. Specifically:

- Parsers, chunker, and services MUST have unit tests (KICKOFF Success Criteria).
- Each interface listed in Principle I MUST have at least one contract test that any future
  implementation MUST also pass (covers the OpenAI/Claude and local/OpenAI-embedding swap).
- Integration tests MUST cover the full ingestion path (upload -> parse -> chunk -> embed
  -> store) and the full QA path (question -> retrieve -> stream) using a temporary
  ChromaDB directory and a stub LLM client.
- Streaming endpoints MUST have a test that asserts the response is incremental (multiple
  SSE chunks observed) and not buffered to completion.
- Red-Green-Refactor: a failing test MUST be committed (or visible in the PR diff) before
  the implementation that makes it pass.

**Rationale**: RAG pipelines silently degrade (bad chunking, embedding drift, prompt
regressions). Contract tests catch provider-swap regressions; streaming tests catch a
common FastAPI/SSE mistake (full-response buffering) that destroys UX.

### III. User Experience Consistency

The end-user experience MUST be predictable across browsers, sessions, and providers:

- Streamed answers MUST appear progressively (first token visible within 2 s of `/ask`
  acceptance under normal load); buffered "appear all at once" responses violate this rule.
- Conversation history MUST be retained for the lifetime of a `session_id` and MUST be
  passed to the LLM on every follow-up turn. Switching providers MUST NOT reset history.
- `/upload` MUST return a stable `document_id` and surface human-readable errors for
  unsupported file types, oversize files, and parse failures (no raw stack traces in the
  HTTP body).
- The chat UI MUST indicate three states explicitly: idle, uploading/processing, streaming.
  Errors MUST be rendered in the chat surface, never as a silent failure.
- Behavior MUST be identical whether `LLM_PROVIDER` is `anthropic` or `openai`, and whether
  `EMBEDDING_PROVIDER` is `local` or `openai`. UX is provider-agnostic.

**Rationale**: A document assistant is judged on perceived responsiveness and trust.
Inconsistent state indication or silent errors break both.

### IV. Performance & Streaming Responsiveness

Performance targets are enforced, not aspirational:

- Ingestion of a 50-page PDF (~25k tokens) MUST complete in under 30 seconds on a laptop-
  class machine using the default `local` embedding provider.
- `/ask` MUST emit the first SSE token within 2 seconds of request acceptance (p95) when
  the LLM provider is reachable.
- Retrieval (vector search for top-K) MUST complete in under 200 ms for collections up
  to 10k chunks.
- Embedding and LLM calls MUST be `async` where the underlying SDK supports it; no
  `requests`-style blocking I/O on the request path.
- Chunking parameters (`CHUNK_SIZE`, `CHUNK_OVERLAP`, `TOP_K_RESULTS`) MUST come from
  config; hard-coded magic numbers in the retrieval/ingestion path are forbidden.
- Any feature that regresses these numbers MUST be flagged in the plan and either fixed
  before merge or accompanied by a written performance-debt entry.

**Rationale**: Streaming, fast retrieval, and async I/O are the difference between a demo
and a usable tool. Putting numeric thresholds in the constitution makes regressions
reviewable instead of arguable.

### V. Configuration-Driven Extensibility

The system MUST be reconfigurable via `.env` without code changes:

- Switching `LLM_PROVIDER` between `anthropic` and `openai` MUST work with only an env
  change (KICKOFF success criterion). Same for `EMBEDDING_PROVIDER`.
- All tunables (chunk size/overlap, top-K, model names, API keys) MUST live in
  `src/config.py` and be loaded from environment variables with documented defaults.
- New providers MUST be added by implementing the relevant interface plus a factory
  branch, NOT by editing service-layer code.
- `.env.example` MUST stay in sync with `config.py`; a missing example entry for a new
  setting is a merge blocker.

**Rationale**: The provider-swap requirement is a hard success criterion. Treating
config as a first-class extension point is what keeps the codebase honest about it.

## Additional Constraints

**Technology stack** (locked unless amended via Governance):

- Python 3.11+, FastAPI, PyMuPDF (`fitz`), `python-docx`, `sentence-transformers`,
  ChromaDB (file-backed), `anthropic` and `openai` SDKs.
- Docker + docker-compose MUST provide a one-command (`docker compose up`) bring-up that
  serves the app on `localhost:8000`.

**Security**:

- API keys MUST be read only from environment variables; they MUST NOT be logged, echoed
  in error responses, or committed to the repository.
- Uploaded files MUST be size-capped and MIME-validated before parsing; parse errors MUST
  NOT propagate provider stack traces to clients.
- The `/upload` endpoint MUST store files in a non-executable working directory and clean
  them up after ingestion (or document retention behavior in the README if retained).

**Dependencies**:

- Adding a runtime dependency requires (a) a one-line rationale in the plan and (b) a
  check that it does not duplicate an existing capability. "Convenience-only" wrappers
  around the standard library are rejected by default.

## Development Workflow & Quality Gates

- Every PR MUST pass: lint (ruff), type check (mypy/pyright), unit tests, and integration
  tests. CI failures block merge; `--no-verify` is forbidden.
- The plan template's Constitution Check MUST enumerate, per feature, how the change
  satisfies each of the five principles, and MUST list any violation in Complexity
  Tracking with a justification.
- Code review MUST verify: interface boundaries (Principle I), test-first evidence
  (Principle II), UX state handling for user-facing changes (Principle III), perf-impact
  awareness (Principle IV), and config exposure of new tunables (Principle V).
- README MUST stay current: setup instructions, env vars, sample Q&A, and `docker compose
  up` flow are user-facing contracts.

## Governance

This constitution supersedes ad-hoc conventions and informal preferences. Where guidance
conflicts with this document, this document wins.

**Amendment procedure**: Open a PR that (a) edits this file, (b) updates the Sync Impact
Report comment at the top, (c) bumps the version per the policy below, and (d) updates
any dependent templates flagged as ⚠ pending. Amendments require at least one reviewer
who is not the author.

**Versioning policy** (semantic):

- MAJOR: A principle is removed, a NON-NEGOTIABLE constraint is relaxed, or governance
  rules are redefined in a backward-incompatible way.
- MINOR: A new principle or section is added, or an existing principle is materially
  expanded.
- PATCH: Clarifications, wording fixes, or non-semantic refinements.

**Compliance review**: At each `/speckit.plan` invocation, the Constitution Check gate
MUST be executed and recorded. At each `/speckit.tasks` invocation, the generated task
list MUST include explicit test tasks before the implementation tasks they cover
(Principle II). The reviewer of any PR MUST confirm constitution compliance in the
review body; an unmentioned constitution is treated as unverified.

**Runtime guidance**: `KICKOFF.md` is the authoritative scope document for the initial
build; this constitution governs *how* that scope is built. When they appear to conflict,
prefer this constitution and open an amendment PR rather than silently diverging.

**Version**: 1.0.0 | **Ratified**: 2026-05-15 | **Last Amended**: 2026-05-15
