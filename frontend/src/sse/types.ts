import type { Citation } from "../api/generated";

export type { Citation };

export type TokenEvent = { type: "token"; text: string };
export type CitationsEvent = { type: "citations"; citations: Citation[] };
export type DoneEvent = { type: "done"; turn_id: string; stopped: boolean };
export type ErrorEvent = {
  type: "error";
  code?: string;
  message: string;
  request_id?: string;
};

export type SseEvent = TokenEvent | CitationsEvent | DoneEvent | ErrorEvent;
