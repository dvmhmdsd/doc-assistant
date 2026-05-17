import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";

import { server } from "../mocks/server";
import { streamAnswer } from "../../src/api/ask";
import type { SseEvent } from "../../src/sse/types";

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

describe("streaming /ask — incrementality gate (US2)", () => {
  it("dispatches ≥ 2 token events with measurable wall-clock gap BEFORE done", async () => {
    const GAP_MS = 20;
    const enc = new TextEncoder();

    server.use(
      http.post("/ask", () => {
        const stream = new ReadableStream<Uint8Array>({
          async start(controller) {
            controller.enqueue(enc.encode('event: token\ndata: {"text":"He"}\n\n'));
            await sleep(GAP_MS);
            controller.enqueue(enc.encode('event: token\ndata: {"text":"llo "}\n\n'));
            await sleep(GAP_MS);
            controller.enqueue(enc.encode('event: token\ndata: {"text":"world"}\n\n'));
            controller.enqueue(enc.encode("event: citations\ndata: []\n\n"));
            controller.enqueue(
              enc.encode('event: done\ndata: {"turn_id":"t-1","stopped":false}\n\n'),
            );
            controller.close();
          },
        });
        return new HttpResponse(stream, {
          status: 200,
          headers: { "Content-Type": "text/event-stream" },
        });
      }),
    );

    const events: { e: SseEvent; t: number }[] = [];
    const start = performance.now();
    await streamAnswer(
      { session_id: "sid-1", question: "q?" },
      (e) => events.push({ e, t: performance.now() - start }),
      new AbortController().signal,
    );

    const tokens = events.filter((x) => x.e.type === "token");
    const done = events.findIndex((x) => x.e.type === "done");
    expect(tokens.length).toBeGreaterThanOrEqual(2);
    // Both tokens arrived before done.
    const firstTokenIdx = events.findIndex((x) => x.e.type === "token");
    const lastTokenBeforeDoneIdx = events
      .map((x, i) => ({ type: x.e.type, i }))
      .filter((x) => x.type === "token" && x.i < done)
      .pop();
    expect(lastTokenBeforeDoneIdx).toBeDefined();
    expect(lastTokenBeforeDoneIdx!.i).toBeGreaterThan(firstTokenIdx);
    // Measurable gap between the first two tokens.
    const t0 = tokens[0]!.t;
    const t1 = tokens[1]!.t;
    expect(t1 - t0).toBeGreaterThan(0);
  });
});
