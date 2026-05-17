# Doc Assistant

> RAG-powered Q&A over your own PDF and Word documents. Upload a file
> in the browser, ask questions in plain language, watch the answer
> stream back with citations.

FastAPI + ChromaDB + (Anthropic or OpenAI) backend with a React 19 +
Tailwind 4 SPA bundled into the same image. Built deliberately without
LangChain / LlamaIndex / Haystack so the OOP + design-pattern layering
stays readable end to end.

---

## Quickstart

One command. Docker required.

```bash
# 1. Configure
cp .env.example .env
$EDITOR .env       # set ANTHROPIC_API_KEY (or OPENAI_API_KEY)

# 2. Run
docker compose up --build
```

Open **<http://localhost:8000>** in a browser. You see the chat UI:

1. Drag a `.pdf` or `.docx` (≤ 25 MB) onto the upload surface, or click
   **Choose a file**.
2. Wait for the "ready" banner.
3. Type a question, hit **Send**. Answer streams in token-by-token.
   **Cancel** stops mid-stream; partial answer is preserved.

> Port 8000 already taken on your host? Set `APP_HOST_PORT=8088` (or
> any free port) in `.env` and re-run. Container always serves on 8000
> internally; only the host mapping changes.

Healthcheck:

```bash
curl -s http://localhost:8000/healthz
# {"status":"ok","version":"0.1.0"}
```

### Tear down

```bash
docker compose down            # stop containers
docker compose down -v         # also wipe Chroma volume + sessions
```

### Frontend hot-reload (optional)

For SPA development with Vite hot-reload, enable the `dev` compose
profile. Backend stays on the same port; the dev SPA runs separately
at <http://localhost:5173> and proxies API calls into the backend
container.

```bash
docker compose --profile dev up --build
# SPA:     http://localhost:5173   (hot reload, source-mounted)
# Backend: http://localhost:8000   (also serves the production SPA build)
```

### Tests

```bash
docker compose run --rm app pytest                              # backend
docker compose --profile dev run --rm frontend-dev pnpm test -- --run   # frontend
```

---

## Provider swap

LLM and embedding providers are environment switches. No code change,
no rebuild — just restart.

```env
# Defaults
LLM_PROVIDER=anthropic
EMBEDDING_PROVIDER=local

# OpenAI for both
LLM_PROVIDER=openai
EMBEDDING_PROVIDER=openai
```

See [ADR 0005](docs/adr/0005-swappable-llm-embedding-providers.md).

---

## API (alternative to the SPA)

The backend also speaks JSON / SSE directly. Useful for scripted
ingest or as a sanity check before hitting the SPA.

```bash
# Upload
RESP=$(curl -s -X POST -F "file=@sample.pdf" http://localhost:8000/upload)
SESSION_ID=$(echo "$RESP" | jq -r .session_id)

# Ask (SSE stream)
curl -N -X POST \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"$SESSION_ID\",\"question\":\"What is the termination notice period?\"}" \
  http://localhost:8000/ask

# End session (purges chunks + history)
curl -X POST \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"$SESSION_ID\"}" \
  http://localhost:8000/session/end -i
```

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/upload` | Upload PDF / DOCX; returns `session_id` (or honors `X-Session-Id`). |
| `POST` | `/ask` | SSE stream: `token` → `citations` → `done` frames. |
| `GET`  | `/history/{session_id}` | Ordered transcript. |
| `POST` | `/session/end` | Purge a session. |
| `GET`  | `/healthz` | Liveness (unauthenticated). |
| `GET`  | `/metrics` | Prometheus exposition (unauthenticated, loopback). |

Full OpenAPI:
[specs/001-doc-assistant-rag/contracts/openapi.yaml](specs/001-doc-assistant-rag/contracts/openapi.yaml).

No global auth gate (single-tenant demo). Per-session isolation comes
from the opaque server-generated `session_id`. Production deploys MUST
front the API with a reverse proxy / API gateway. ADR-007 captures the
threat model.

---

## Architecture at a glance

```
src/                       # FastAPI backend
├── api/                   FastAPI app factory, routes, deps, errors
├── parsers/               Strategy: PdfParser, DocxParser + factory
├── chunker/               Token-aware sliding window (tiktoken cl100k_base)
├── embeddings/            Strategy: Local (sentence-transformers) / OpenAI
├── vector_store/          Repository: ChromaVectorStore (file-backed)
├── llm/                   Strategy: Anthropic / OpenAI + bounded retry
├── services/              Facades: ingestion, qa, sessions, prompts
├── history/               Repository: InMemoryConversationStore
├── observability/         structlog JSON + Prometheus metrics
└── config.py              pydantic-settings Settings

frontend/                  # React 19 + Tailwind 4 SPA (Vite 8)
├── src/
│   ├── api/               typed HTTP + SSE client (no Authorization header)
│   ├── sse/               eventsource-parser wiring + typed events
│   ├── state/             useReducer session machine + sessionStorage
│   └── components/        UploadSurface, Composer, Transcript, Turn, …
└── tests/                 Vitest 4 + RTL + MSW 2 + streaming gate
```

| Pattern    | Where | Why |
|---|---|---|
| Strategy   | parsers, embeddings, llm | Interchangeable impls behind one ABC |
| Factory    | parsers/factory, embeddings/factory, llm/factory | Resolve impl from config |
| Repository | vector_store, history | Swap storage without touching services |
| Facade     | services/ingestion, services/qa | Hide multi-step pipelines |

Deeper dive in
[docs/explanation/architecture.md](docs/explanation/architecture.md)
(system flow + Mermaid sequence diagrams).

---

## Documentation map

Organised along the [Diataxis](https://diataxis.fr/) pillars:

- **Run it** — this file +
  [docs/how-to/quickstart.md](docs/how-to/quickstart.md) (5-minute
  runbook) + [docs/how-to/sample-queries.md](docs/how-to/sample-queries.md)
  (worked transcripts, raw SSE frames).
- **How it works** —
  [docs/explanation/architecture.md](docs/explanation/architecture.md),
  [docs/explanation/sequence-diagrams.md](docs/explanation/sequence-diagrams.md),
  and [docs/adr/](docs/adr/) for the architecture decision records.
- **Spec → Plan → Tasks** —
  [specs/001-doc-assistant-rag/](specs/001-doc-assistant-rag/) (backend)
  and [specs/002-chat-ui/](specs/002-chat-ui/) (SPA).
- **Conventions** — [CLAUDE.md](CLAUDE.md) (paid-for-in-mistakes rules).
- **Non-negotiable principles** —
  [.specify/memory/constitution.md](.specify/memory/constitution.md).

---

## Configuration reference

Every tunable lives in [`src/config.py:Settings`](src/config.py) and
is mirrored in [`.env.example`](.env.example).

| Env var | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` | `anthropic` | `anthropic` or `openai`. |
| `EMBEDDING_PROVIDER` | `local` | `local` or `openai`. |
| `ANTHROPIC_API_KEY` | — | Required when `LLM_PROVIDER=anthropic`. |
| `OPENAI_API_KEY` | — | Required when either provider is `openai`. |
| `LLM_MODEL` | provider default | e.g. `claude-opus-4-7`. |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | |
| `CHUNK_SIZE` | `500` | tokens per chunk (tiktoken cl100k_base). |
| `CHUNK_OVERLAP` | `50` | overlap tokens. |
| `TOP_K_RESULTS` | `5` | retrieval depth. |
| `MAX_UPLOAD_BYTES` | `26214400` (25 MiB) | upload cap. |
| `CHROMA_PERSIST_DIR` | `./chroma_data` | vector store directory. |
| `UPLOAD_TMP_DIR` | `./uploads_tmp` | upload spool. |
| `RETRY_BUDGET_SECONDS` | `5.0` | wall-clock cap on provider retries. |
| `RETRY_ATTEMPTS` | `3` | 1 initial + 2 retries. |
| `RETRY_MAX_WAIT` | `2.0` | per-attempt backoff cap. |
| `APP_HOST_PORT` | `8000` | host port mapping (container always 8000). |
| `VITE_API_BASE_URL` | — | Dev-only: proxy target for `frontend-dev`. |
