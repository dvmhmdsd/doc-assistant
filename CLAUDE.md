<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
under `specs/001-doc-assistant-rag/` (spec.md → plan.md → research.md →
data-model.md → contracts/ → tasks.md). The constitution at
`.specify/memory/constitution.md` is non-negotiable.
<!-- SPECKIT END -->

# Project conventions — do NOT violate

These rules were paid for in past mistakes during this project. Read
before writing any new module in `src/` or any new test.

## Imports

- **Use RELATIVE imports inside `src/`**: `from ..foo.bar import X`,
  `from .base import Y`. Do NOT write `from src.foo.bar import X` —
  every reviewer flags it and mypy strict + ruff `I` complain.
- **Top-level package imports** for runtime deps. No `try: import foo`
  inside `__init__`. If the dep is in `pyproject.toml`, it is required;
  pretending it's optional just delays errors from module load to
  instantiation.
- **Never name a module after a PyPI package you also import.** E.g.,
  do NOT create `src/embeddings/openai.py` if you also need
  `from openai import AsyncOpenAI`. The local module shadows the
  package. Use `openai_client.py`, `anthropic_client.py`, etc.

## Typing

- `mypy --strict` is on. Annotate everything. No untyped `def f(cfg=None)`
  — write `def f(cfg: Settings | None = None)`.
- Use **built-in generics** on Python 3.11: `list[X]`, `tuple[X, Y]`,
  `dict[K, V]`, `X | None`. Do NOT use `typing.List/Tuple/Dict/Optional`.
  Ruff `UP006`/`UP007`/`UP035` will flag.
- After an `await` boundary, **assign to a local var** when you need
  pyright to narrow `Optional[T]` → `T`. Re-reading `self._field` after
  await does not narrow.

## Error handling

- **No bare `except Exception:`** as control flow. Catch the specific
  exception class (e.g., `chromadb.errors.NotFoundError`,
  `httpx.TimeoutException`) and let unknowns bubble. Swallowing all
  errors merges "expected miss" with "broken dependency" and hides
  regressions.
- **No try/except fallback signatures** to absorb library API drift
  (e.g., calling `delete_collection` then `_delete_collection` as
  fallback). Pin the dep version and use the documented method.
  Private-method calls (leading underscore) are forbidden in this
  codebase.
- Route-layer errors MUST raise an `AppError` subclass from
  `src/api/errors.py`. The handler renders the OpenAPI `Error` schema
  with the right status. Bare `ValueError` / `RuntimeError` reach the
  client as 500 + stack trace, violating FR-011.

## Configuration

- All tunables come from `src/config.py` (`Settings`). No
  `os.environ[...]` reads sprinkled in service or provider code.
  Constitution Principle V — single config surface.
- Add a new env var by editing **both** `Settings` and `.env.example`
  in the same change. A missing `.env.example` entry is a merge blocker.

## Async I/O

- FastAPI handlers and provider clients are `async`. **Never** call
  `asyncio.run` or `loop.run_until_complete` from inside a request —
  it crashes on a running event loop.
- For sync libraries (`sentence_transformers`, `chromadb`), offload to
  a worker thread via `asyncio.to_thread(...)`. Block the request path
  and you blow the p95 first-token SLO.
- Properties that need lazy async initialization should EITHER be
  `async` methods OR raise `RuntimeError` until a prior async call has
  populated the cached value. Do NOT trigger `run_until_complete` from
  a sync property.

## Interfaces, factories, design patterns

- Cross-layer calls go through the five interfaces in
  `contracts/interfaces.md`. Concrete classes are injected by factories;
  service code does NOT branch on `cfg.llm_provider` /
  `cfg.embedding_provider`. Adding a new provider = new class + factory
  branch + test. Zero edits in `services/`.
- Use `client.get_or_create_collection(...)` (atomic, server-side) over
  hand-rolled `try get_collection; except: create_collection` patterns.
- Guard first-create races on shared resources with an `asyncio.Lock`
  (one per key, e.g., per `session_id`).
- Defensive `text = x or ""` coerce is forbidden when the upstream type
  is non-optional. Let mypy catch the contract violation.

## Vector store / retrieval specifics

- Chroma collections MUST be created with `metadata={"hnsw:space":
  "cosine"}`. Default L2 makes embedding similarity rankings worse.
- `VectorStore.search` returns **similarity** ∈ `[0, 1]`, larger = more
  similar. Chroma returns **distance** internally — convert with
  `similarity = max(0.0, 1.0 - distance)` before exposing. Returning
  raw distances inverts ranking everywhere downstream
  (`QAService`, `Citation.score`).
- Metadata stored alongside chunks omits keys whose value is `None`
  (Chroma cannot reliably filter "field IS NULL"). Sparse metadata,
  not `None`-valued fields.
- `drop_session` is idempotent: catch only `NotFoundError`, not all
  exceptions.

## Chunking specifics

- Token-based, not character-based. Use `tiktoken cl100k_base` (R-012).
- `chunk_id` is deterministic: `f"{document_id}:{sequence_index}"`.
  No UUIDs — re-ingest must produce the same ids.
- Concatenate segments with `"\n\n"` separator so tokens never merge
  across logical paragraph/page boundaries.
- Pick chunk locator (page/section) from the segment with **maximum
  character overlap** with the chunk, not the segment containing
  `char_start`.

## Embeddings specifics

- Local: `sentence-transformers`. Inference offloaded to threads. Batch
  internally (default 64) to bound peak memory.
- OpenAI: official `AsyncOpenAI` SDK. Batch in groups of 100 (per-
  request limits). API key from `Settings`, not `os.environ`.
- Known-model dimension lookup (`text-embedding-3-small` = 1536,
  `-large` = 3072). Do NOT guess `1536` as a default; raise until
  measured or known.

## Docker

- `docker compose up` is the ONLY supported start path. No
  `uvicorn`/`npm run dev` instructions in README or quickstart.
- Tests run in the image: `docker compose run --rm app pytest`.
- Install CPU torch **before** `pip install -e ".[dev]"` so
  sentence-transformers' transitive `torch` resolves to the CPU wheel
  instead of pulling ~2 GB of `nvidia-*` CUDA wheels. CUDA wheels are
  dead weight on Apple Silicon / CPU hosts and a frequent
  build-timeout source.

## Logging & secrets

- `structlog` JSON lines, one log per request, with `request_id`,
  event, `session_handle_hash` (NEVER the raw handle), timing fields.
- Logs MUST NOT contain: API keys, raw session handles, raw question
  or answer text, document contents.
- Error responses MUST NOT contain stack traces or provider IDs.

## Testing

- Test-first per Principle II. Failing test committed BEFORE the
  implementation that makes it pass.
- A test file that contains only `pytest.fail("not implemented")` is
  **scaffolding**, not a written test — leave the task unchecked.
- Mock external HTTP with `respx` so tests run offline. Tests that
  `pytest.skipif(... or not OPENAI_API_KEY)` silently skip in CI =
  effectively absent. Don't ship those.
- Mock heavy local deps (e.g., `sentence_transformers`) via
  `monkeypatch.setitem(sys.modules, "package", fake_module)` so the
  test does not download model weights.
- Streaming-endpoint integration tests MUST assert ≥ 2 SSE token
  frames arrived incrementally — not "the body is non-empty".

## Tasks tracking

- Mark `[x]` in `specs/001-doc-assistant-rag/tasks.md` only when the
  task's full contract is satisfied (real assertions, no
  `pytest.fail`, no partial implementations). If the file exists but
  is a stub or has known gaps, the task is NOT done.

## Commit conventions

- Conventional Commits style: `feat(parsers): ...`, `build: ...`,
  `docs(001): ...`. Subject ≤ 72 chars. Body explains the why.
- Never commit `.env`. Use `.env.example` for the public template.
- Never commit `.claude/settings.local.json` (user-local).
