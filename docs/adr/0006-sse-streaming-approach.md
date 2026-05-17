# ADR 0006: Server-Sent Events (SSE) for /ask Streaming

## Status

Accepted — 2026-05-16.

## Context

`/ask` must stream LLM token deltas to the browser as they arrive
(FR-006). The first visible token must reach the user within 2 s in
95% of attempts (SC-002). The transport must:

- be **unidirectional** (server → client) — we never need
  client→server messages within a stream;
- support **multiple event types** so the client can distinguish a
  token delta, a citations payload, the end of the stream, and an
  error frame;
- have **native browser support** without ad-hoc framing libraries
  (the React/Tailwind SPA in feature 002 is the primary consumer);
- be **trivial to test** — an integration test must be able to read
  the response chunk-by-chunk and assert at least two `event: token`
  frames arrived before the response closed.

`StreamingResponse` errors mid-stream are particularly important. The
spec (FR-011, T051) says a recoverable error must render inline in the
chat surface — not drop the connection silently.

## Decision

Server-Sent Events over HTTP, served by FastAPI's
`StreamingResponse(media_type="text/event-stream")` in
`src/api/routes/ask.py`. Four frame types match the OpenAPI contract:

| Event | Data |
|---|---|
| `token` | `{"text": "<delta>"}` |
| `citations` | `Citation[]` — emitted exactly once before `done` |
| `done` | `{"turn_id": "...", "stopped": false}` |
| `error` | `{"code": "...", "message": "..."}` — terminates the stream |

The `_wrap_stream` helper around the QA service catches `AppError` and
unexpected exceptions during iteration and emits a single `event:
error` frame so the client receives a clean failure, not a half-formed
HTTP response.

## Alternatives Considered

**WebSockets.** Bidirectional, framed, with reconnection helpers in
every major framework. Rejected because the bidirectional channel is
unnecessary for our one-way token stream, the handshake adds latency,
and reconnection-state management has no payoff for our model. SSE
gets the same job done with less surface area.

**HTTP chunked transfer with a custom delimiter.** Works. Forces us to
reinvent event-type framing, error semantics, and parsing helpers that
SSE already standardises. The browser-native `EventSource` becomes
useless. Rejected.

**gRPC streaming.** Excellent for service-to-service. Overkill for a
single-machine browser demo, and browser clients need a `grpc-web`
proxy which itself is an operational dependency we deliberately
avoided everywhere else.

## Consequences

**Positive.** Native `EventSource` works in every modern browser; the
React client uses `fetch` + `ReadableStream` instead (chosen for
cancellation control via `AbortController` — see feature 002).
Testing is trivial: `httpx.AsyncClient.stream` exposes the
raw response body line by line, and the `__anext__` /
`async for` shape of the QA service maps 1:1 to the wire format. The
explicit `error` frame keeps FR-011 honest — failures are visible in
the transcript, not invisible disconnections.

**Negative.** `EventSource` cannot set request headers, so the SPA
uses `fetch` + `ReadableStream` instead. That is a known papercut
documented in feature 002's spec, not a blocker. Mid-stream
errors cannot be retried by the framework — the connection has already
been committed to a 200 OK; our retry policy lives entirely *before*
the first byte is sent (`open_with_retry` in `src/llm/retry.py`). This
is an intentional tradeoff: once tokens start flowing, the user is
better served by an inline error frame than by a transparent retry that
might duplicate content.

## References

- `specs/001-doc-assistant-rag/research.md` — R-005.
- `specs/001-doc-assistant-rag/spec.md` — FR-006, FR-011, FR-021,
  SC-002.
- `specs/001-doc-assistant-rag/contracts/openapi.yaml` — SSE frame
  definitions.
- `src/api/routes/ask.py` — implementation including `_wrap_stream`.
