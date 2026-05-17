import type { AskRequest, Error as ApiErrorBody } from "./generated";
import { ApiError } from "./client";
import { parseStream } from "../sse/parser";
import type { SseEvent } from "../sse/types";

export async function streamAnswer(
  req: AskRequest,
  onEvent: (e: SseEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  const res = await fetch("/ask", {
    method: "POST",
    headers: {
      Accept: "text/event-stream",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(req),
    signal,
  });

  if (!res.ok) {
    let body: ApiErrorBody | null = null;
    try {
      const contentType = res.headers.get("content-type") ?? "";
      if (contentType.toLowerCase().includes("application/json")) {
        body = (await res.json()) as ApiErrorBody;
      }
    } catch {
      body = null;
    }
    const message = body?.message ?? res.statusText ?? `HTTP ${res.status}`;
    throw new ApiError(message, res.status, body?.code, body?.request_id);
  }

  if (!res.body) return;
  await parseStream(res.body, onEvent, signal);
}
