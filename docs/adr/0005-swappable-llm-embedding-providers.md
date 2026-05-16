# ADR 0005: Swappable LLM and Embedding Providers via Config Only

## Status

Accepted — 2026-05-16.

## Context

FR-010 mandates that the operator can swap the AI text-generation
provider and the embedding provider by editing `.env` and restarting —
no source code edits, no rebuild beyond restart. SC-005 makes that a
verifiable acceptance criterion: any pair `(LLM_PROVIDER,
EMBEDDING_PROVIDER) ∈ {anthropic, openai} × {local, openai}` must pass
the same upload + ask flow.

Constitution Principle V (Configuration-Driven Extensibility)
reinforces this: every tunable comes from a single config surface
(`src/config.py:Settings`), and a new provider is added by implementing
the relevant interface plus a factory branch — not by editing the
service layer.

## Decision

Two abstract base classes:

- `LLMClient` (`src/llm/base.py`) — `stream_chat(messages) ->
  AsyncIterator[str]`, plus a `model_name` property.
- `EmbeddingProvider` (`src/embeddings/base.py`) — `embed(texts) ->
  list[list[float]]`, plus `model_name` and `dimensions`.

Two concrete implementations of each, all four discoverable today:

- `AnthropicLLMClient`, `OpenAILLMClient`
- `LocalEmbeddingProvider` (sentence-transformers), `OpenAIEmbeddingProvider`

Selection happens at startup in two factory functions:

- `make_llm_client(cfg)` in `src/llm/factory.py`
- `make_embedding_provider(cfg)` in `src/embeddings/factory.py`

Both validate the relevant API key is present before constructing the
client. Both are wrapped in `@lru_cache(maxsize=1)` providers in
`src/api/deps.py` so every route resolves the same singleton.

Service-layer code (`IngestionService`, `QAService`, `SessionService`)
MUST NOT import provider-specific modules or branch on
`cfg.llm_provider` / `cfg.embedding_provider`. The audit in T059
enforces this.

## Alternatives Considered

**Provider-agnostic libraries (e.g. LiteLLM).** Solves the same
problem with one line of import. Rejected because (a) it defeats the
point of demonstrating the Strategy + Factory patterns that the project
exists to showcase, (b) it adds an abstraction we do not control and
cannot audit, and (c) provider behaviour differences (streaming
semantics, citation conventions, system-prompt handling) are exactly
the things we want explicit in our own contract.

**Hard-coding Anthropic only.** Simplest implementation. Fails FR-010
outright and removes the safety net against single-provider risk
(cost, outage, deprecation).

**Per-route conditionals.** `if cfg.llm_provider == "openai": ...` in
the route layer. Pollutes every consumer with provider choice and
guarantees a forgotten branch on the next add. Principle V violation.

## Consequences

**Positive.** SC-005 is verifiable from a four-cell test matrix in
`tests/integration/test_provider_swap.py` (deferred to a follow-up
integration commit). The contract tests
(`tests/contract/test_llm_contract.py`,
`tests/contract/test_embedding_contract.py`) run against both impls
through the same suite, so any new provider must pass them too.
Adding a future provider (Bedrock, Mistral, a private endpoint) is a
new file plus a factory branch plus a contract-test parameter — and
zero edits in the service layer.

**Negative.** The interfaces must stay narrow enough that every
provider can implement them cleanly. We deliberately do NOT surface
provider-specific features that have no cross-provider equivalent:
structured-output mode, tool-use, response-format JSON, model-specific
sampling knobs. Anyone needing those would extend the contract
explicitly (and update both implementations) rather than punching
through to the SDK directly. Our retry policy
(`src/llm/retry.py`) is similarly provider-agnostic — it inspects a
duck-typed `status_code` attribute on raised exceptions rather than
catching SDK-specific error classes.

## References

- `specs/001-doc-assistant-rag/research.md` — R-004.
- `specs/001-doc-assistant-rag/spec.md` — FR-010, SC-005.
- `.specify/memory/constitution.md` — Principle V.
- `src/llm/factory.py`, `src/embeddings/factory.py`, `src/api/deps.py`.
- `contracts/interfaces.md` — `LLMClient`, `EmbeddingProvider`.
