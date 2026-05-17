import { describe, expect, it } from "vitest";

import { sessionReducer, type SessionState } from "../../../src/state/session";

function readyFixture(): SessionState {
  return {
    kind: "ready",
    sessionId: "sid-1",
    document: {
      documentId: "doc-1",
      filename: "paper.pdf",
      byteSize: 1024,
      chunkCount: 2,
      pageCount: 1,
      ingestedAt: "2026-05-17T00:00:00.000Z",
    },
    transcript: [],
  };
}

function runCycle(state: SessionState, q: string, a: string, turnId: string): SessionState {
  let s = sessionReducer(state, {
    type: "submitQuestion",
    text: q,
    controller: new AbortController(),
  });
  s = sessionReducer(s, { type: "tokenAppended", text: a });
  s = sessionReducer(s, { type: "streamDone", turnId, stopped: false });
  return s;
}

describe("session reducer — multi-turn (US3)", () => {
  it("three submit→stream→done cycles produce 6 turns in chronological order", () => {
    let state: SessionState = readyFixture();
    state = runCycle(state, "Q1", "A1", "t-1");
    state = runCycle(state, "Q2", "A2", "t-2");
    state = runCycle(state, "Q3", "A3", "t-3");

    expect(state.kind).toBe("ready");
    if (state.kind !== "ready") throw new Error("kind narrowed");
    expect(state.transcript).toHaveLength(6);
    expect(state.transcript.map((t) => `${t.role}:${t.content}`)).toEqual([
      "user:Q1",
      "assistant:A1",
      "user:Q2",
      "assistant:A2",
      "user:Q3",
      "assistant:A3",
    ]);
  });

  it("between cycles, state.kind is 'ready' — composer would re-enable", () => {
    let state: SessionState = readyFixture();
    state = runCycle(state, "Q1", "A1", "t-1");
    expect(state.kind).toBe("ready");
    state = runCycle(state, "Q2", "A2", "t-2");
    expect(state.kind).toBe("ready");
  });
});
