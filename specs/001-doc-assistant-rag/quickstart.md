# Quickstart: Doc Assistant

**Phase**: 1
**Branch**: `001-doc-assistant-rag`
**Target audience**: a developer landing on the repo cold, wanting to run the
assistant locally and exercise the API in under 5 minutes (SC-008).

---

## 1. Prerequisites

- Docker + Docker Compose (recommended path), OR
- Python 3.11+ and Node 20+ (manual path, for hacking on backend / frontend
  separately).

You will need an Anthropic API key (default LLM provider) or an OpenAI key
(alternative). Local embeddings need no key.

---

## 2. Configure environment

```bash
cp .env.example .env
$EDITOR .env
```

Set, at minimum:

```env
APP_SHARED_TOKEN=replace-me-with-a-long-random-string
LLM_PROVIDER=anthropic                # or: openai
EMBEDDING_PROVIDER=local              # or: openai
ANTHROPIC_API_KEY=sk-ant-...          # if LLM_PROVIDER=anthropic
# OPENAI_API_KEY=sk-...               # if LLM_PROVIDER=openai or EMBEDDING_PROVIDER=openai
```

Optional tunables (defaults shown):

```env
CHUNK_SIZE=500
CHUNK_OVERLAP=50
TOP_K_RESULTS=5
MAX_UPLOAD_BYTES=26214400             # 25 MB
LLM_MODEL=claude-opus-4-7
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

The server refuses to start if `APP_SHARED_TOKEN` is empty.

---

## 3. Start the app

```bash
docker compose up --build
```

App is available at <http://localhost:8000>. The frontend is served at `/`, API
under the same origin.

(Manual path, two terminals, for hacking:)

```bash
# terminal 1 — backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn src.main:app --reload --port 8000

# terminal 2 — frontend (feature 002)
cd frontend && npm ci && npm run dev
```

---

## 4. Verify

```bash
curl -s http://localhost:8000/healthz
# {"status":"ok","version":"0.1.0"}
```

---

## 5. End-to-end smoke (covers User Story 1 + 2)

Replace `$TOKEN` with the value of `APP_SHARED_TOKEN`.

### 5.1 Upload a document

```bash
RESP=$(curl -s -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@sample.pdf" \
  http://localhost:8000/upload)
echo "$RESP" | jq
SESSION_ID=$(echo "$RESP" | jq -r .session_id)
```

Expected: ingest completes in < 30 s for a 50-page PDF (SC-001) and returns
`session_id`, `document_id`, `chunk_count`, and per-stage timings.

### 5.2 Ask a question (SSE stream)

```bash
curl -N -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "$(jq -n --arg sid "$SESSION_ID" --arg q "What is the termination notice period?" \
        '{session_id:$sid, question:$q}')" \
  http://localhost:8000/ask
```

You should see frames like:

```
event: token
data: {"text": "The "}

event: token
data: {"text": "termination notice "}

...

event: citations
data: [{"chunk_id": "...", "document_id": "...", "locator": "page 12", "score": 0.82}]

event: done
data: {"turn_id": "...", "stopped": false}
```

First `token` frame should arrive in under 2 s (SC-002).

### 5.3 Follow-up (User Story 2)

```bash
curl -N -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "$(jq -n --arg sid "$SESSION_ID" \
        '{session_id:$sid, question:"Can it be extended?"}')" \
  http://localhost:8000/ask
```

The answer should resolve "it" against the previous turn.

### 5.4 History

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/history/$SESSION_ID | jq
```

### 5.5 End the session (purge)

```bash
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"$SESSION_ID\"}" \
  http://localhost:8000/session/end -i
# HTTP/1.1 204 No Content
```

After this, both `/ask` and `/history/{sid}` on that handle return 404.

---

## 6. Swap providers (User Story 3, SC-005)

```bash
# .env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

Restart:

```bash
docker compose restart
```

Repeat section 5. No code change required.

---

## 7. Observability

```bash
curl -s http://localhost:8000/metrics | grep doc_assistant_
```

Look for `doc_assistant_time_to_first_token_seconds_bucket`,
`doc_assistant_ingest_seconds_*`, `doc_assistant_retrieval_seconds_*`,
`doc_assistant_provider_retry_total{provider="anthropic"}`.

Logs are JSON lines on stdout, one per request, with `request_id`, `event`,
`session_handle_hash`, and timing fields. No secrets, no raw session handles, no
document text.

---

## 8. Run the tests

```bash
pip install -e ".[dev]"
pytest                       # full suite (contract + integration + unit)
pytest tests/contract        # interface contracts
pytest tests/integration     # full flow incl. streaming
pytest tests/unit            # parsers, chunker, retry policy
```

Streaming integration test asserts ≥ 2 SSE `token` frames arrived before stream
end (constitution Principle II).

---

## 9. Trouble?

- `401 unauthorized` → `Authorization: Bearer $TOKEN` missing or wrong.
- `413 payload_too_large` → file over `MAX_UPLOAD_BYTES`.
- `415 unsupported_media_type` → not PDF or DOCX.
- `400 bad_request` with "not extractable" → likely a scan-only PDF; OCR is out
  of scope in v1.
- `502 upstream_unavailable` on `/ask` → all provider retries exhausted; check
  the provider key and retry.
