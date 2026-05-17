import { createParser, type EventSourceMessage } from "eventsource-parser";

import type { Citation, SseEvent } from "./types";

type CitationsPayload = Citation[];
type DonePayload = { turn_id: string; stopped?: boolean };
type ErrorPayload = { code?: string; message: string; request_id?: string };
type TokenPayload = { text: string };

let warnedUnknownEvent = false;

function dispatch(name: string, raw: string, onEvent: (e: SseEvent) => void): void {
  switch (name) {
    case "token": {
      const data = JSON.parse(raw) as TokenPayload;
      if (typeof data.text === "string") onEvent({ type: "token", text: data.text });
      return;
    }
    case "citations": {
      const data = JSON.parse(raw) as CitationsPayload;
      onEvent({ type: "citations", citations: data });
      return;
    }
    case "done": {
      const data = JSON.parse(raw) as DonePayload;
      onEvent({ type: "done", turn_id: data.turn_id, stopped: Boolean(data.stopped) });
      return;
    }
    case "error": {
      const data = JSON.parse(raw) as ErrorPayload;
      const evt: SseEvent = {
        type: "error",
        message: data.message,
        ...(data.code !== undefined ? { code: data.code } : {}),
        ...(data.request_id !== undefined ? { request_id: data.request_id } : {}),
      };
      onEvent(evt);
      return;
    }
    default: {
      if (!warnedUnknownEvent) {
        warnedUnknownEvent = true;
        console.warn("[sse] unknown event type:", name);
      }
    }
  }
}

export async function parseStream(
  stream: ReadableStream<Uint8Array>,
  onEvent: (e: SseEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();

  const parser = createParser({
    onEvent(ev: EventSourceMessage) {
      const name = ev.event ?? "message";
      try {
        dispatch(name, ev.data, onEvent);
      } catch (err) {
        console.warn("[sse] failed to parse event", name, err);
      }
    },
  });

  const onAbort = (): void => {
    void reader.cancel();
  };
  if (signal.aborted) {
    void reader.cancel();
  } else {
    signal.addEventListener("abort", onAbort, { once: true });
  }

  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      parser.feed(decoder.decode(value, { stream: true }));
    }
  } finally {
    signal.removeEventListener("abort", onAbort);
    try {
      reader.releaseLock();
    } catch {
      // already released
    }
  }
}
