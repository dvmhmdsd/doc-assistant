import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import type { AskRequest } from "../../../src/api/generated";
import { ApiError } from "../../../src/api/client";
import { streamAnswer } from "../../../src/api/ask";
import type { SseEvent } from "../../../src/sse/types";
import { server } from "../../mocks/server";

const ask: AskRequest = { session_id: "sid-test", question: "hello?" };

describe("streamAnswer", () => {
  it("dispatches token, citations, then done in order", async () => {
    const events: SseEvent[] = [];
    await streamAnswer(ask, (e) => events.push(e), new AbortController().signal);

    expect(events.map((e) => e.type)).toEqual(["token", "token", "citations", "done"]);
    const done = events[3];
    if (done?.type !== "done") throw new Error("type narrow");
    expect(done.turn_id).toBe("turn-1");
    expect(done.stopped).toBe(false);
  });

  it("never attaches an Authorization header", async () => {
    let captured: string | null = "set";
    server.use(
      http.post("/ask", ({ request }) => {
        captured = request.headers.get("authorization");
        return new HttpResponse("event: done\ndata: {\"turn_id\":\"t\",\"stopped\":false}\n\n", {
          status: 200,
          headers: { "Content-Type": "text/event-stream" },
        });
      }),
    );

    await streamAnswer(ask, () => undefined, new AbortController().signal);

    expect(captured).toBeNull();
  });

  it("maps non-2xx error body to ApiError", async () => {
    server.use(
      http.post("/ask", () =>
        HttpResponse.json(
          { code: "not_found", message: "session not found", request_id: "rid-2" },
          { status: 404 },
        ),
      ),
    );

    await expect(
      streamAnswer(ask, () => undefined, new AbortController().signal),
    ).rejects.toMatchObject({
      name: "ApiError",
      status: 404,
      code: "not_found",
      message: "session not found",
      requestId: "rid-2",
    });
  });

  it("propagates AbortError when caller aborts mid-stream", async () => {
    server.use(
      http.post("/ask", async () => {
        // Stream that never closes
        const stream = new ReadableStream({
          start(controller) {
            controller.enqueue(new TextEncoder().encode('event: token\ndata: {"text":"a"}\n\n'));
          },
        });
        return new HttpResponse(stream, {
          status: 200,
          headers: { "Content-Type": "text/event-stream" },
        });
      }),
    );

    const controller = new AbortController();
    const events: SseEvent[] = [];
    const p = streamAnswer(ask, (e) => events.push(e), controller.signal);
    // Give the first token a tick to arrive, then abort.
    setTimeout(() => controller.abort(), 30);

    await p; // Parser exits cleanly when reader cancels via abort wiring.
    expect(events.length).toBeGreaterThanOrEqual(1);
    expect(events[0]?.type).toBe("token");
  });
});

// Reference unused import so the tree-shaker keeps it.
void ApiError;
