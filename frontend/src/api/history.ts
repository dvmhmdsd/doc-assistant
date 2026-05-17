import { fetchJson } from "./client";
import type { HistoryResponse } from "./generated";

export function fetchHistory(sessionId: string): Promise<HistoryResponse> {
  return fetchJson<HistoryResponse>(`/history/${encodeURIComponent(sessionId)}`);
}
