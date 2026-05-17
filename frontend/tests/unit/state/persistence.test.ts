import { beforeEach, describe, expect, it } from "vitest";

import { clearSession, loadSession, saveSession } from "../../../src/state/persistence";
import type { DocumentMeta } from "../../../src/state/session";

const SAMPLE_DOC: DocumentMeta = {
  documentId: "doc-1",
  filename: "paper.pdf",
  byteSize: 1024,
  chunkCount: 2,
  pageCount: 1,
  ingestedAt: "2026-05-17T00:00:00.000Z",
};

beforeEach(() => sessionStorage.clear());

describe("persistence (sessionStorage)", () => {
  it("returns null when nothing is stored", () => {
    expect(loadSession()).toBeNull();
  });

  it("round-trips the session id + document meta as a JSON blob", () => {
    saveSession({ sessionId: "sid-xyz", document: SAMPLE_DOC });
    const raw = sessionStorage.getItem("doc-assistant.session");
    expect(raw).not.toBeNull();
    expect(raw!.startsWith("{")).toBe(true);
    expect(loadSession()).toEqual({ sessionId: "sid-xyz", document: SAMPLE_DOC });
  });

  it("clears the stored payload", () => {
    saveSession({ sessionId: "sid-xyz", document: SAMPLE_DOC });
    clearSession();
    expect(loadSession()).toBeNull();
  });

  it("returns null on a legacy bare-string payload (incompatible schema)", () => {
    sessionStorage.setItem("doc-assistant.session", "sid-legacy");
    expect(loadSession()).toBeNull();
  });

  it("returns null on a malformed JSON payload", () => {
    sessionStorage.setItem("doc-assistant.session", "{not-json");
    expect(loadSession()).toBeNull();
  });
});
