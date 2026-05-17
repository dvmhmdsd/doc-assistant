import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";

import { server } from "../mocks/server";
import { fetchHistory } from "../../src/api/history";
import { sessionReducer, type SessionState } from "../../src/state/session";
import {
  ConversationTurnRoleEnum,
  ConversationTurnStateEnum,
  type HistoryResponse,
} from "../../src/api/generated";

function emptyState(): SessionState {
  return { kind: "empty" };
}

const SAMPLE_HISTORY: HistoryResponse = {
  session_id: "sid-1",
  turns: [
    {
      turn_id: "t-1",
      role: ConversationTurnRoleEnum.User,
      content: "First question?",
      citations: null,
      created_at: "2026-05-17T00:00:01.000Z",
      state: null,
    },
    {
      turn_id: "t-2",
      role: ConversationTurnRoleEnum.Assistant,
      content: "First answer.",
      citations: [
        { chunk_id: "c1", document_id: "d1", locator: "p.1", score: 0.9 },
      ],
      created_at: "2026-05-17T00:00:02.000Z",
      state: ConversationTurnStateEnum.Complete,
    },
    {
      turn_id: "t-3",
      role: ConversationTurnRoleEnum.User,
      content: "Follow-up?",
      citations: null,
      created_at: "2026-05-17T00:00:03.000Z",
      state: null,
    },
    {
      turn_id: "t-4",
      role: ConversationTurnRoleEnum.Assistant,
      content: "Second answer.",
      citations: null,
      created_at: "2026-05-17T00:00:04.000Z",
      state: ConversationTurnStateEnum.Complete,
    },
  ],
};

describe("GET /history/{session_id} contract (US3)", () => {
  it("fetchHistory parses the wire shape and reducer rehydrates into ready with the transcript", async () => {
    server.use(
      http.get("/history/sid-1", () => HttpResponse.json(SAMPLE_HISTORY, { status: 200 })),
    );

    const resp = await fetchHistory("sid-1");
    expect(resp.session_id).toBe("sid-1");
    expect(resp.turns).toHaveLength(4);

    const next = sessionReducer(emptyState(), {
      type: "rehydrated",
      response: {
        sessionId: resp.session_id,
        document: {
          documentId: "doc-1",
          filename: "paper.pdf",
          byteSize: 0,
          chunkCount: 0,
          pageCount: null,
          ingestedAt: "2026-05-17T00:00:00.000Z",
        },
        transcript: resp.turns.map((t) => ({
          id: t.turn_id,
          role: t.role,
          content: t.content,
          citations: t.citations ?? null,
          state: t.state ?? "complete",
          createdAt: t.created_at,
        })),
      },
    });

    expect(next.kind).toBe("ready");
    if (next.kind !== "ready") throw new Error("kind narrowed");
    expect(next.transcript).toHaveLength(4);
    expect(next.transcript[0]?.role).toBe("user");
    expect(next.transcript[1]?.citations).toHaveLength(1);
    // The streaming state machine guarantees no AbortController on ready.
    expect("controller" in next).toBe(false);
  });

  it("404 surfaces as a typed ApiError", async () => {
    server.use(
      http.get("/history/missing", () =>
        HttpResponse.json(
          { code: "not_found", message: "Session not found." },
          { status: 404 },
        ),
      ),
    );
    await expect(fetchHistory("missing")).rejects.toMatchObject({
      status: 404,
      message: "Session not found.",
    });
  });
});
