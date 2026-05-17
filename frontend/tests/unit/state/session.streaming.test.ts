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

describe("session reducer — streaming transitions (US2)", () => {
  it("ready → streaming appends a user turn synchronously and attaches the AbortController", () => {
    const controller = new AbortController();
    const next = sessionReducer(readyFixture(), {
      type: "submitQuestion",
      text: "What is this about?",
      controller,
    });

    expect(next.kind).toBe("streaming");
    if (next.kind !== "streaming") throw new Error("kind narrowed");
    expect(next.controller).toBe(controller);
    // submitQuestion seeds both the user turn and an empty assistant turn.
    expect(next.transcript).toHaveLength(2);
    expect(next.transcript[0]).toMatchObject({
      role: "user",
      content: "What is this about?",
      state: "sent",
    });
    expect(next.transcript[1]).toMatchObject({
      role: "assistant",
      content: "",
      state: "streaming",
    });
  });

  it("streaming → ready on streamDone(stopped=false) finalizes the trailing turn as complete", () => {
    const controller = new AbortController();
    let state = sessionReducer(readyFixture(), {
      type: "submitQuestion",
      text: "Q",
      controller,
    });
    state = sessionReducer(state, { type: "tokenAppended", text: "Hello " });
    state = sessionReducer(state, { type: "tokenAppended", text: "world" });
    state = sessionReducer(state, {
      type: "streamDone",
      turnId: "turn-1",
      stopped: false,
    });

    expect(state.kind).toBe("ready");
    if (state.kind !== "ready") throw new Error("kind narrowed");
    // user + assistant turns
    expect(state.transcript).toHaveLength(2);
    const assistant = state.transcript[1];
    expect(assistant?.role).toBe("assistant");
    expect(assistant?.content).toBe("Hello world");
    expect(assistant?.state).toBe("complete");
    expect(assistant?.id).toBe("turn-1");
  });

  it("streaming → ready (cancel) marks the trailing turn stopped and preserves partial content", () => {
    const controller = new AbortController();
    let state = sessionReducer(readyFixture(), {
      type: "submitQuestion",
      text: "Q",
      controller,
    });
    state = sessionReducer(state, { type: "tokenAppended", text: "Hel" });
    state = sessionReducer(state, { type: "streamCancelled" });

    expect(state.kind).toBe("ready");
    if (state.kind !== "ready") throw new Error("kind narrowed");
    const assistant = state.transcript[1];
    expect(assistant?.state).toBe("stopped");
    expect(assistant?.content).toBe("Hel");
  });

  it("streaming → error snapshots a ready previous and marks the trailing turn errored", () => {
    const controller = new AbortController();
    let state = sessionReducer(readyFixture(), {
      type: "submitQuestion",
      text: "Q",
      controller,
    });
    state = sessionReducer(state, { type: "tokenAppended", text: "partial" });
    state = sessionReducer(state, {
      type: "streamErrored",
      message: "Provider unavailable",
    });

    expect(state.kind).toBe("error");
    if (state.kind !== "error") throw new Error("kind narrowed");
    expect(state.message).toBe("Provider unavailable");
    expect(state.previous.kind).toBe("ready");
    if (state.previous.kind !== "ready") throw new Error("previous kind narrowed");
    const assistant = state.previous.transcript[1];
    expect(assistant?.state).toBe("errored");
    expect(assistant?.content).toBe("partial");
  });

  it("citationsReceived attaches citations to the trailing assistant turn", () => {
    const controller = new AbortController();
    let state = sessionReducer(readyFixture(), {
      type: "submitQuestion",
      text: "Q",
      controller,
    });
    state = sessionReducer(state, { type: "tokenAppended", text: "ans" });
    state = sessionReducer(state, {
      type: "citationsReceived",
      citations: [{ chunk_id: "c1", document_id: "doc-1", locator: "p.1", score: 0.9 }],
    });

    if (state.kind !== "streaming") throw new Error("expected streaming");
    expect(state.transcript[1]?.citations).toEqual([
      { chunk_id: "c1", document_id: "doc-1", locator: "p.1", score: 0.9 },
    ]);
  });

  it("ignores submitQuestion fired while not in ready (warns + no-op)", () => {
    const controller = new AbortController();
    const next = sessionReducer({ kind: "empty" }, {
      type: "submitQuestion",
      text: "Q",
      controller,
    });
    expect(next).toEqual({ kind: "empty" });
  });
});
