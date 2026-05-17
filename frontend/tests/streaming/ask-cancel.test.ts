import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";

import { server } from "../mocks/server";
import { streamAnswer } from "../../src/api/ask";
import { sessionReducer, type SessionState } from "../../src/state/session";
import type { SseEvent } from "../../src/sse/types";

function readyState(): SessionState {
  return {
    kind: "ready",
    sessionId: "sid-1",
    document: {
      documentId: "doc-1",
      filename: "x.pdf",
      byteSize: 1,
      chunkCount: 1,
      pageCount: 1,
      ingestedAt: "2026-05-17T00:00:00.000Z",
    },
    transcript: [],
  };
}

describe("streaming /ask — cancellation (US2)", () => {
  it("AbortController halts the reader, reducer marks trailing turn stopped, partial content preserved", async () => {
    const enc = new TextEncoder();
    const controller = new AbortController();

    server.use(
      http.post("/ask", () => {
        const stream = new ReadableStream<Uint8Array>({
          async start(c) {
            c.enqueue(enc.encode('event: token\ndata: {"text":"He"}\n\n'));
            // Wait until aborted; never emit done.
            await new Promise<void>((resolve) => {
              const tick = (): void => {
                if (controller.signal.aborted) return resolve();
                setTimeout(tick, 5);
              };
              tick();
            });
            c.close();
          },
        });
        return new HttpResponse(stream, {
          status: 200,
          headers: { "Content-Type": "text/event-stream" },
        });
      }),
    );

    let state = sessionReducer(readyState(), {
      type: "submitQuestion",
      text: "Q?",
      controller,
    });

    const stream = streamAnswer(
      { session_id: "sid-1", question: "Q?" },
      (e: SseEvent) => {
        if (e.type === "token") state = sessionReducer(state, { type: "tokenAppended", text: e.text });
        if (e.type === "done")
          state = sessionReducer(state, {
            type: "streamDone",
            turnId: e.turn_id,
            stopped: e.stopped,
          });
      },
      controller.signal,
    );

    // Let the first token land.
    await new Promise((r) => setTimeout(r, 30));
    controller.abort();
    state = sessionReducer(state, { type: "streamCancelled" });

    // streamAnswer rejects with AbortError on cancel — swallow it.
    await stream.catch(() => undefined);

    expect(state.kind).toBe("ready");
    if (state.kind !== "ready") throw new Error("kind narrowed");
    const assistant = state.transcript[1];
    expect(assistant?.role).toBe("assistant");
    expect(assistant?.state).toBe("stopped");
    expect(assistant?.content).toBe("He");
  });
});
