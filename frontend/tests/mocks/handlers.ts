import { http, HttpResponse } from "msw";

import type {
  HistoryResponse,
  UploadResponse,
} from "../../src/api/generated";

/**
 * Default MSW handlers — happy paths only. Individual tests override via
 * `server.use(...)` for specific failure scenarios.
 */

const sampleUploadResponse: UploadResponse = {
  session_id: "sid-test",
  document_id: "doc-test",
  filename: "sample.pdf",
  mime_type: "application/pdf",
  byte_size: 1024,
  page_count: 1,
  chunk_count: 3,
  ingested_at: "2026-05-17T00:00:00.000Z",
};

const sampleHistory: HistoryResponse = {
  session_id: "sid-test",
  turns: [],
};

export const handlers = [
  http.post("/upload", () => HttpResponse.json(sampleUploadResponse, { status: 200 })),

  http.post("/ask", () => {
    const body = [
      'event: token\ndata: {"text":"hello "}\n\n',
      'event: token\ndata: {"text":"world"}\n\n',
      'event: citations\ndata: []\n\n',
      'event: done\ndata: {"turn_id":"turn-1","stopped":false}\n\n',
    ].join("");
    return new HttpResponse(body, {
      status: 200,
      headers: { "Content-Type": "text/event-stream" },
    });
  }),

  http.get("/history/:sessionId", () => HttpResponse.json(sampleHistory, { status: 200 })),

  http.post("/session/end", () => new HttpResponse(null, { status: 204 })),
];
