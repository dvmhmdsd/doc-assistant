import { describe, expect, it } from "vitest";

import { parseStream } from "../../../src/sse/parser";
import type { SseEvent } from "../../../src/sse/types";

function streamFromString(s: string): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(s));
      controller.close();
    },
  });
}

async function collect(input: string): Promise<SseEvent[]> {
  const out: SseEvent[] = [];
  await parseStream(streamFromString(input), (e) => out.push(e), new AbortController().signal);
  return out;
}

describe("parseStream", () => {
  it("emits token, citations, done in order from a canned SSE body", async () => {
    const body = [
      'event: token\ndata: {"text":"hello "}\n\n',
      'event: token\ndata: {"text":"world"}\n\n',
      'event: citations\ndata: [{"chunk_id":"c1","document_id":"d1","locator":"page 1","score":0.5}]\n\n',
      'event: done\ndata: {"turn_id":"t1","stopped":false}\n\n',
    ].join("");

    const events = await collect(body);

    expect(events.map((e) => e.type)).toEqual(["token", "token", "citations", "done"]);
    const done = events[3];
    if (done?.type !== "done") throw new Error("type narrow");
    expect(done.stopped).toBe(false);
    expect(done.turn_id).toBe("t1");
  });

  it("ignores comment frames (keepalive)", async () => {
    const body = [
      ": keepalive\n\n",
      'event: token\ndata: {"text":"x"}\n\n',
      'event: done\ndata: {"turn_id":"t","stopped":false}\n\n',
    ].join("");

    const events = await collect(body);

    expect(events.map((e) => e.type)).toEqual(["token", "done"]);
  });

  it("emits an error event when the server sends event: error", async () => {
    const body =
      'event: error\ndata: {"code":"upstream_unavailable","message":"boom","request_id":"r1"}\n\n';

    const events = await collect(body);

    expect(events).toHaveLength(1);
    const evt = events[0];
    if (evt?.type !== "error") throw new Error("type narrow");
    expect(evt.message).toBe("boom");
    expect(evt.code).toBe("upstream_unavailable");
    expect(evt.request_id).toBe("r1");
  });

  it("does not throw on unknown event type", async () => {
    const body = 'event: weird\ndata: {"any":"thing"}\n\n';

    const events = await collect(body);

    expect(events).toEqual([]);
  });

  it("cancels read when signal aborts before stream completes", async () => {
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode('event: token\ndata: {"text":"a"}\n\n'));
        // Intentionally never close — abort must terminate parseStream.
      },
    });

    const controller = new AbortController();
    const events: SseEvent[] = [];
    const p = parseStream(stream, (e) => events.push(e), controller.signal);
    setTimeout(() => controller.abort(), 20);

    await p;
    expect(events.length).toBeGreaterThanOrEqual(1);
  });
});
