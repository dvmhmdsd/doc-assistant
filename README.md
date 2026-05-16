# Doc Assistant

> RAG-powered Q&A over your own PDF and Word documents. Upload a file,
> ask questions in plain language, watch the answer stream back with
> citations to the source passages.

A self-contained FastAPI + ChromaDB + (Anthropic or OpenAI) stack with
a swappable React + Tailwind chat client. Built deliberately without
LangChain / LlamaIndex / Haystack so the OOP + design-pattern layering
stays readable end to end.

---

## Quickstart (Docker only)

`docker compose up` is the only supported run path. Do not invoke
`uvicorn` or `npm run dev` directly.

```bash
# 1. Configure
cp .env.example .env
$EDITOR .env   # at minimum set APP_SHARED_TOKEN + an LLM API key

# 2. Run
docker compose up --build
```

App available at <http://localhost:8000> (or set `APP_HOST_PORT=8088`
in env to remap if 8000 is taken by another local service).

Healthcheck:

```bash
curl -s http://localhost:8000/healthz
# {"status":"ok","version":"0.1.0"}
```

End-to-end smoke (see [specs/001-doc-assistant-rag/quickstart.md](specs/001-doc-assistant-rag/quickstart.md)
for the full runbook):

```bash
export TOKEN=$(grep APP_SHARED_TOKEN .env | cut -d= -f2)

# Upload
RESP=$(curl -s -X POST -H "Authorization: Bearer $TOKEN" \
  -F "file=@sample.pdf" http://localhost:8000/upload)
SESSION_ID=$(echo "$RESP" | jq -r .session_id)

# Ask (SSE stream)
curl -N -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"$SESSION_ID\",\"question\":\"What is the termination notice period?\"}" \
  http://localhost:8000/ask

# End the session (purges chunks + history)
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"$SESSION_ID\"}" \
  http://localhost:8000/session/end -i
```

Tests run in the same image:

```bash
docker compose run --rm app pytest
```

---

## Provider swap

Switching LLM or embedding provider is a `.env` edit + restart. No
code changes, no rebuild beyond restart.

```env
# Default
LLM_PROVIDER=anthropic
EMBEDDING_PROVIDER=local

# Or: OpenAI for both
LLM_PROVIDER=openai
EMBEDDING_PROVIDER=openai
```

See [ADR 0005](docs/adr/0005-swappable-llm-embedding-providers.md) for
the design.

---

## Architecture at a glance

```
src/
├── api/                FastAPI app factory, routes, deps, errors
│   ├── app.py          create_app() — middleware + handler + routes
│   ├── deps.py         lru_cache DI providers (singletons)
│   ├── errors.py       AppError hierarchy + handler
│   └── routes/         upload, ask (SSE), session/end, history, metrics
├── parsers/            Strategy pattern: PdfParser, DocxParser + factory
├── chunker/            Token-aware sliding window (tiktoken cl100k_base)
├── embeddings/         Strategy: Local (sentence-transformers) / OpenAI
├── vector_store/       Repository: ChromaVectorStore (file-backed)
├── llm/                Strategy: Anthropic / OpenAI + bounded retry
├── services/           Facades: ingestion, qa, sessions, prompts
├── history/            Repository: InMemoryConversationStore
├── observability/      structlog JSON logs + Prometheus metrics
├── config.py           pydantic-settings Settings
└── main.py             `app = create_app()`
```

| Pattern    | Where | Why |
|---|---|---|
| Strategy   | parsers, embeddings, llm | Interchangeable impls behind one ABC |
| Factory    | parsers/factory, embeddings/factory, llm/factory | Resolve impl from config |
| Repository | vector_store, history | Swap storage without touching services |
| Facade     | services/ingestion, services/qa | Hide multi-step pipelines |

---

## API

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/upload` | Upload a PDF or DOCX; returns a `document_id` (and creates a session if no `X-Session-Id` header). |
| `POST` | `/ask` | Ask a question; SSE stream of `token` → `citations` → `done` frames. |
| `GET`  | `/history/{session_id}` | Fetch the ordered transcript for a session. |
| `POST` | `/session/end` | Purge a session's chunks + history. |
| `GET`  | `/healthz` | Liveness (unauthenticated). |
| `GET`  | `/metrics` | Prometheus exposition (unauthenticated, loopback). |

Full OpenAPI:
[specs/001-doc-assistant-rag/contracts/openapi.yaml](specs/001-doc-assistant-rag/contracts/openapi.yaml).

All endpoints except `/healthz` and `/metrics` require
`Authorization: Bearer <APP_SHARED_TOKEN>`.

---

## Documentation map

- **What it does** — this file + [KICKOFF.md](KICKOFF.md).
- **What was decided and why** — [docs/adr/](docs/adr/) (six ADRs +
  index).
- **Spec → Plan → Tasks** —
  [specs/001-doc-assistant-rag/](specs/001-doc-assistant-rag/).
  The spec is the contract; the plan covers tech context + structure;
  tasks track work in dependency order.
- **Project conventions to NOT violate** — [CLAUDE.md](CLAUDE.md).
- **Non-negotiable principles** —
  [.specify/memory/constitution.md](.specify/memory/constitution.md).

---

## Configuration reference

Every tunable lives in [`src/config.py:Settings`](src/config.py) and is
mirrored in [`.env.example`](.env.example). The server refuses to start
if `APP_SHARED_TOKEN` is empty.

| Env var | Default | Purpose |
|---|---|---|
| `APP_SHARED_TOKEN` | (required) | Bearer token gate for all API calls. |
| `LLM_PROVIDER` | `anthropic` | `anthropic` or `openai`. |
| `EMBEDDING_PROVIDER` | `local` | `local` (sentence-transformers) or `openai`. |
| `ANTHROPIC_API_KEY` | — | Required when `LLM_PROVIDER=anthropic`. |
| `OPENAI_API_KEY` | — | Required when either provider is `openai`. |
| `LLM_MODEL` | provider default | e.g. `claude-opus-4-7`. |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | |
| `CHUNK_SIZE` | `500` | tokens per chunk (tiktoken cl100k_base). |
| `CHUNK_OVERLAP` | `50` | overlap tokens. |
| `TOP_K_RESULTS` | `5` | retrieval depth. |
| `MAX_UPLOAD_BYTES` | `26214400` (25 MiB) | upload cap. |
| `CHROMA_PERSIST_DIR` | `./chroma_data` | vector store directory. |
| `UPLOAD_TMP_DIR` | `./uploads_tmp` | temp spool for incoming uploads. |
| `RETRY_BUDGET_SECONDS` | `5.0` | wall-clock cap on provider retries. |
| `RETRY_ATTEMPTS` | `3` | total attempts (1 initial + 2 retries). |
| `RETRY_MAX_WAIT` | `2.0` | per-attempt exp-backoff cap. |

---

## Status

This is feature **001-doc-assistant-rag** plus the Docker scaffolding
for feature **002-chat-ui**. The React + Tailwind SPA itself is still
backlogged — the backend serves the API surface but no chat UI is bundled
yet (production Dockerfile is single-stage backend-only until 002
lands; multi-stage build returns when the SPA scaffolds).

Tests run via `docker compose run --rm app pytest`. Integration tests
across the wire are deferred; unit + contract coverage exercises every
interface implementation directly.
