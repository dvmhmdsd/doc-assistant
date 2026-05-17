# Sample queries and outputs

Worked examples that satisfy the "Sample queries and outputs"
deliverable in [`original-requirements.md`](../../original-requirements.md).
Each example shows the exact HTTP request, the expected response shape,
and (for `/ask`) the SSE wire format.

The fixture used below is a 5-page redline of a Mutual Non-Disclosure
Agreement (NDA). Substitute your own PDF/DOCX; the response shapes are
identical regardless of content.

```bash
# Common environment for every block below
export TOKEN=$(grep '^APP_SHARED_TOKEN=' .env | cut -d= -f2-)
export BASE=http://localhost:8000          # or 8088 if APP_HOST_PORT is set
```

---

## 1. Upload — start a new session

```bash
curl -s -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@samples/nda.pdf" \
  "$BASE/upload" | jq .
```

Response:

```json
{
  "session_id": "NI9j7pGB_s4izZOHYGXYK6S1GfyNgqMzoWpyyhpRJIs",
  "document_id": "4cb030bd83c83ea7fffef4fb8724f04a00b3b9a1927d25d3541b26cdde72eedc",
  "filename": "nda.pdf",
  "mime_type": "application/pdf",
  "byte_size": 24611,
  "page_count": 5,
  "chunk_count": 14,
  "ingested_timing_ms": {
    "parse_ms": 38,
    "chunk_ms": 11,
    "embed_ms": 412,
    "store_ms": 64,
    "total_ms": 525
  },
  "ingested_at": "2026-05-17T10:14:02.118233+00:00"
}
```

Notes:

- `session_id` is unguessable (`secrets.token_urlsafe(32)`). Capture it
  for the rest of the session.
- `document_id` is a deterministic SHA-256 of the file bytes — uploading
  the same file again produces the same id.
- `chunk_count` reflects token-aware chunking with `CHUNK_SIZE=500`,
  `CHUNK_OVERLAP=50`.
- First-time call may take 2-3 minutes (sentence-transformers model
  download); subsequent calls finish in well under a second.

```bash
SID=NI9j7pGB_s4izZOHYGXYK6S1GfyNgqMzoWpyyhpRJIs
```

---

## 2. Ask — factual question (P1)

```bash
curl -N -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"$SID\",\"question\":\"What is the termination notice period?\"}" \
  "$BASE/ask"
```

SSE stream (raw bytes; the SPA parses these via `fetch` +
`ReadableStream`):

```
event: token
data: {"text": "The "}

event: token
data: {"text": "termination "}

event: token
data: {"text": "notice "}

event: token
data: {"text": "period "}

event: token
data: {"text": "is "}

event: token
data: {"text": "thirty (30) days, "}

event: token
data: {"text": "in writing, "}

event: token
data: {"text": "as set out in Section 7."}

event: citations
data: [{"chunk_id":"4cb030bd...:8","document_id":"4cb030bd...","locator":"page 4","score":0.847},
       {"chunk_id":"4cb030bd...:9","document_id":"4cb030bd...","locator":"page 4","score":0.812},
       {"chunk_id":"4cb030bd...:5","document_id":"4cb030bd...","locator":"page 3","score":0.611}]

event: done
data: {"turn_id": "0c8e1aab-...", "stopped": false}
```

Invariants visible:

- First `event: token` arrives well under 2 s (SC-002) once the
  provider connection is open.
- `event: citations` appears **exactly once**, **before** `event: done`.
- Each citation carries the OpenAPI shape: `chunk_id`, `document_id`,
  human-readable `locator`, and `score` (cosine similarity in
  `[0, 1]`).
- `done.stopped` is `false` for a normal completion (a user-cancelled
  stream would set it to `true` and `state="stopped"` on the persisted
  turn).

---

## 3. Ask — follow-up using prior context (P2)

```bash
curl -N -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"$SID\",\"question\":\"Can it be extended?\"}" \
  "$BASE/ask"
```

Selected frames:

```
event: token
data: {"text": "Yes — "}

event: token
data: {"text": "the thirty-day "}

event: token
data: {"text": "termination notice "}

event: token
data: {"text": "may be extended by mutual written consent of both parties "}

event: token
data: {"text": "(Section 7.3)."}

event: citations
data: [{"chunk_id":"4cb030bd...:9","document_id":"4cb030bd...","locator":"page 4","score":0.823}]

event: done
data: {"turn_id": "7b1c244c-...", "stopped": false}
```

Why this works without restating the topic: `QAService.answer` loads
the last 20 prior turns from `ConversationStore` and threads them as
alternating `user`/`assistant` messages **before** the new question.
The LLM sees "What is the termination notice period?" + its own prior
answer + "Can it be extended?", so the pronoun *it* resolves to the
30-day notice period.

---

## 4. Ask — answer not in the document (honest "I don't know")

```bash
curl -N -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"$SID\",\"question\":\"What is the governing jurisdiction's official population?\"}" \
  "$BASE/ask"
```

```
event: token
data: {"text": "I "}

event: token
data: {"text": "don't "}

event: token
data: {"text": "know."}

event: citations
data: []

event: done
data: {"turn_id": "ad33f0e1-...", "stopped": false}
```

The system prompt in `src/services/prompts.py` mandates "I don't know."
when the retrieved chunks do not contain the answer (FR-007). No
fabricated facts. The citations frame is still emitted (per the
contract) but may be empty.

---

## 5. History — fetch the transcript

```bash
curl -s -H "Authorization: Bearer $TOKEN" "$BASE/history/$SID" | jq .
```

```json
{
  "session_id": "NI9j7pGB_s4izZOHYGXYK6S1GfyNgqMzoWpyyhpRJIs",
  "turns": [
    {
      "turn_id": "06b3e7f2-...",
      "role": "user",
      "content": "What is the termination notice period?",
      "citations": null,
      "created_at": "2026-05-17T10:14:48.301412+00:00",
      "state": null
    },
    {
      "turn_id": "0c8e1aab-...",
      "role": "assistant",
      "content": "The termination notice period is thirty (30) days, in writing, as set out in Section 7.",
      "citations": [
        {"chunk_id":"4cb030bd...:8","document_id":"4cb030bd...","locator":"page 4","score":0.847},
        {"chunk_id":"4cb030bd...:9","document_id":"4cb030bd...","locator":"page 4","score":0.812},
        {"chunk_id":"4cb030bd...:5","document_id":"4cb030bd...","locator":"page 3","score":0.611}
      ],
      "created_at": "2026-05-17T10:14:50.018997+00:00",
      "state": "complete"
    },
    {
      "turn_id": "f8a4b2e5-...",
      "role": "user",
      "content": "Can it be extended?",
      "citations": null,
      "created_at": "2026-05-17T10:15:12.487031+00:00",
      "state": null
    },
    {
      "turn_id": "7b1c244c-...",
      "role": "assistant",
      "content": "Yes — the thirty-day termination notice may be extended by mutual written consent of both parties (Section 7.3).",
      "citations": [
        {"chunk_id":"4cb030bd...:9","document_id":"4cb030bd...","locator":"page 4","score":0.823}
      ],
      "created_at": "2026-05-17T10:15:14.602118+00:00",
      "state": "complete"
    },
    {
      "turn_id": "92e1aaff-...",
      "role": "user",
      "content": "What is the governing jurisdiction's official population?",
      "citations": null,
      "created_at": "2026-05-17T10:15:40.117244+00:00",
      "state": null
    },
    {
      "turn_id": "ad33f0e1-...",
      "role": "assistant",
      "content": "I don't know.",
      "citations": [],
      "created_at": "2026-05-17T10:15:41.029866+00:00",
      "state": "complete"
    }
  ]
}
```

Chronological order; citations populated only on assistant turns; the
assistant turn's `state` is `"complete"` (or `"stopped"` / `"errored"`
if the stream was cancelled or hit an error).

---

## 6. End the session — purge chunks and history

```bash
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"$SID\"}" \
  -i "$BASE/session/end"
```

```
HTTP/1.1 204 No Content
```

After this, both `/ask` and `/history/{SID}` on this handle return a
typed 404 (`{"code":"not_found","message":"session not found",
"request_id":"..."}`). The ChromaDB collection and the in-memory
history are gone (FR-019).

---

## 7. Error surfaces (illustrative)

| Scenario | Status | Body shape |
|---|---|---|
| Missing `Authorization` header | `401` | `{"code":"unauthorized","message":"missing or malformed Authorization header","request_id":"..."}` |
| Wrong token | `401` | `{"code":"unauthorized","message":"invalid token","request_id":"..."}` |
| Upload non-PDF/DOCX (e.g. `.txt`) | `415` | `{"code":"unsupported_media_type","message":"unsupported file type: 'notes.txt' (mime='text/plain')","request_id":"..."}` |
| Upload over `MAX_UPLOAD_BYTES` | `413` | `{"code":"payload_too_large","message":"file exceeds 26214400-byte limit","request_id":"..."}` |
| Scan-only PDF (no text layer) | `400` | `{"code":"bad_request","message":"uploaded document contains no extractable text","request_id":"..."}` |
| Provider unreachable, retry budget exhausted | `502` | `{"code":"upstream_unavailable","message":"anthropic call exceeded 5.0s retry budget","request_id":"..."}` |
| Mid-stream provider failure | SSE `event: error` | `data: {"code":"upstream_unavailable","message":"..."}` |
| Unknown session id on `/ask`, `/history`, `/session/end` | `404` | `{"code":"not_found","message":"session not found","request_id":"..."}` |

Every error body matches the OpenAPI `Error` schema. Stack traces and
provider details never appear in responses (FR-011, FR-015). `request_id`
correlates the response to the matching log line emitted by
`structlog`.

---

## Reproducing these outputs locally

1. Bring up the container: `docker compose up --build`. Wait until
   `curl http://localhost:8000/healthz` returns `200`.
2. Put a `.env` in place with a real `APP_SHARED_TOKEN` and (for
   sections 2–4) a real `ANTHROPIC_API_KEY` **or** `OPENAI_API_KEY`.
   Without one, `/ask` will return the `502 upstream_unavailable`
   error shape from the table above — which is itself a valid sample
   demonstrating FR-021.
3. Drop any PDF or DOCX into `samples/` and run the curl commands.
   Token counts, chunk counts, and per-stage timings will vary by
   document. The schema shapes will not.

For the full operational walkthrough see
[quickstart.md](./quickstart.md); for invariants and frame ordering see
[the sequence diagrams](../explanation/sequence-diagrams.md).
