import type { Citation } from "../api/generated";

export type TurnState = "sent" | "streaming" | "complete" | "stopped" | "errored";

export type Turn = {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[] | null;
  state: TurnState;
  createdAt: string;
};

export function appendUserTurn(transcript: Turn[], text: string): Turn[] {
  const turn: Turn = {
    id: crypto.randomUUID(),
    role: "user",
    content: text,
    citations: null,
    state: "sent",
    createdAt: new Date().toISOString(),
  };
  return [...transcript, turn];
}

export function startAssistantTurn(transcript: Turn[]): Turn[] {
  const turn: Turn = {
    id: crypto.randomUUID(),
    role: "assistant",
    content: "",
    citations: null,
    state: "streaming",
    createdAt: new Date().toISOString(),
  };
  return [...transcript, turn];
}

/**
 * Mutates the trailing turn's `content` in place and returns the same
 * array reference. This is the streaming hot path — copy-on-write here
 * regenerates the entire array per SSE frame (~1k frames per answer)
 * and stalls React reconciliation for long answers. Consumers wanting
 * a reactive view should observe the DOM node directly via a ref
 * (see component-side `Turn.tsx` in T040).
 */
export function appendTokenInPlace(transcript: Turn[], text: string): Turn[] {
  const trailing = transcript[transcript.length - 1];
  if (trailing && trailing.role === "assistant") {
    trailing.content = trailing.content + text;
    return transcript;
  }
  // No trailing assistant turn yet — create one with this delta.
  const turn: Turn = {
    id: crypto.randomUUID(),
    role: "assistant",
    content: text,
    citations: null,
    state: "streaming",
    createdAt: new Date().toISOString(),
  };
  return [...transcript, turn];
}

export function setCitations(transcript: Turn[], citations: Citation[]): Turn[] {
  if (transcript.length === 0) return transcript;
  const last = transcript[transcript.length - 1];
  if (!last) return transcript;
  const updated: Turn = { ...last, citations };
  return [...transcript.slice(0, -1), updated];
}

export function finalizeTrailingTurn(
  transcript: Turn[],
  state: "complete" | "stopped" | "errored",
  turnId?: string,
): Turn[] {
  if (transcript.length === 0) return transcript;
  const last = transcript[transcript.length - 1];
  if (!last) return transcript;
  const updated: Turn = { ...last, state, id: turnId ?? last.id };
  return [...transcript.slice(0, -1), updated];
}
