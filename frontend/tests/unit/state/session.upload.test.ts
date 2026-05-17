import { beforeEach, describe, expect, it, vi } from "vitest";

import { saveSession } from "../../../src/state/persistence";
import {
  type Action,
  type DocumentMeta,
  type SessionState,
  sessionReducer,
} from "../../../src/state/session";

const document: DocumentMeta = {
  documentId: "doc-1",
  filename: "doc.pdf",
  byteSize: 1024,
  chunkCount: 1,
  pageCount: null,
  ingestedAt: "2026-05-17T00:00:00.000Z",
};

const empty: SessionState = { kind: "empty" };

beforeEach(() => {
  sessionStorage.clear();
  vi.restoreAllMocks();
});

describe("sessionReducer — upload flow (T025)", () => {
  it("empty -> uploading -> ready and persists session_id on success", () => {
    const started: Action = { type: "uploadStarted", filename: "doc.pdf" };
    const uploading = sessionReducer(empty, started);
    expect(uploading.kind).toBe("uploading");

    const succeeded: Action = {
      type: "uploadSucceeded",
      response: { sessionId: "sid-123", document },
    };
    const ready = sessionReducer(uploading, succeeded);
    expect(ready.kind).toBe("ready");
    if (ready.kind !== "ready") throw new Error("type narrow");
    expect(ready.sessionId).toBe("sid-123");

    // Persistence is a side effect performed by the consumer (App.tsx),
    // not the reducer. Verify the consumer pattern stores the payload.
    saveSession({ sessionId: ready.sessionId, document: ready.document });
    const raw = sessionStorage.getItem("doc-assistant.session");
    expect(raw).not.toBeNull();
    expect(JSON.parse(raw!).sessionId).toBe("sid-123");
  });

  it("uploading -> error snapshots previous=empty and leaves storage untouched", () => {
    // Pre-load sessionStorage to confirm the reducer itself never clears it
    // (the side-effect lives in the consumer, gated on previous === empty).
    sessionStorage.setItem("doc-assistant.session", "stale-handle");

    const uploading: SessionState = { kind: "uploading", filename: "doc.pdf", progress: 0 };
    const failed: Action = { type: "uploadFailed", message: "ingest failed" };
    const errored = sessionReducer(uploading, failed);

    expect(errored.kind).toBe("error");
    if (errored.kind !== "error") throw new Error("type narrow");
    expect(errored.message).toBe("ingest failed");
    expect(errored.previous).toEqual({ kind: "empty" });

    // Reducer is pure; storage is the consumer's responsibility.
    expect(sessionStorage.getItem("doc-assistant.session")).toBe("stale-handle");
  });
});
