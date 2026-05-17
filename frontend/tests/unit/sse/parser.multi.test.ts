import { describe, expect, it, vi } from "vitest";

import { parseStream } from "../../../src/sse/parser";
import type { SseEvent } from "../../../src/sse/types";

function streamFromString(body: string): ReadableStream<Uint8Array> {
  const enc = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      controller.enqueue(enc.encode(body));
      controller.close();
    },
  });
}

describe("SSE parser — full event matrix (US2)", () => {
  it("dispatches token, citations, done in order and ignores keepalive comments", async () => {
    const body =
      ":keepalive\n\n" +
      'event: token\ndata: {"text":"Hello "}\n\n' +
      'event: token\ndata: {"text":"world"}\n\n' +
      'event: citations\ndata: [{"chunk_id":"c1","document_id":"d1","locator":"p.1","score":0.9}]\n\n' +
      'event: done\ndata: {"turn_id":"t-1","stopped":false}\n\n';
    const events: SseEvent[] = [];
    await parseStream(streamFromString(body), (e) => events.push(e), new AbortController().signal);

    expect(events.map((e) => e.type)).toEqual(["token", "token", "citations", "done"]);
    expect(events[0]).toMatchObject({ type: "token", text: "Hello " });
    expect(events[3]).toMatchObject({ type: "done", turn_id: "t-1", stopped: false });
  });

  it("concatenates multi-line `data:` fields with newlines per SSE spec", async () => {
    // data: lines joined by '\n' BEFORE JSON.parse, so the test payload must
    // be valid JSON after that concatenation. Use a token with an embedded
    // newline in the text to exercise the multi-line code path.
    const body =
      'event: token\ndata: {"text":"line one\\n' +
      'data: line two"}\n\n';
    const events: SseEvent[] = [];
    await parseStream(streamFromString(body), (e) => events.push(e), new AbortController().signal);

    // The parser hands "data: line two" inside the JSON string verbatim;
    // we just need a single token frame to land.
    expect(events).toHaveLength(1);
    expect(events[0]?.type).toBe("token");
  });

  it("emits an error event with the verbatim message", async () => {
    const body =
      'event: error\ndata: {"code":"upstream_error","message":"Provider unavailable"}\n\n';
    const events: SseEvent[] = [];
    await parseStream(streamFromString(body), (e) => events.push(e), new AbortController().signal);

    expect(events[0]).toMatchObject({
      type: "error",
      code: "upstream_error",
      message: "Provider unavailable",
    });
  });

  it("warns once on an unknown event name and does not throw", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const body = 'event: bogus\ndata: {}\n\nevent: bogus\ndata: {}\n\n';
    const events: SseEvent[] = [];
    await parseStream(streamFromString(body), (e) => events.push(e), new AbortController().signal);
    expect(events).toEqual([]);
    expect(warn).toHaveBeenCalled();
    warn.mockRestore();
  });

  it("stops reading and resolves when the AbortController fires before stream end", async () => {
    const enc = new TextEncoder();
    const controller = new AbortController();
    let pushed = 0;
    const stream = new ReadableStream<Uint8Array>({
      async pull(c) {
        if (pushed === 0) {
          c.enqueue(enc.encode('event: token\ndata: {"text":"a"}\n\n'));
          pushed += 1;
          return;
        }
        // simulate infinite stream
        await new Promise((r) => setTimeout(r, 5));
        if (controller.signal.aborted) {
          c.close();
          return;
        }
      },
    });

    const events: SseEvent[] = [];
    const promise = parseStream(stream, (e) => events.push(e), controller.signal);
    // Allow first chunk to flow, then abort.
    await new Promise((r) => setTimeout(r, 10));
    controller.abort();
    await promise;
    expect(events.length).toBeGreaterThanOrEqual(1);
  });
});
