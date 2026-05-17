import { describe, expect, it } from "vitest";

import type { Citation } from "../../../src/api/generated";
import {
  appendTokenInPlace,
  appendUserTurn,
  finalizeTrailingTurn,
  setCitations,
  startAssistantTurn,
  type Turn,
} from "../../../src/state/transcript";

const cit: Citation = {
  chunk_id: "c1",
  document_id: "d1",
  locator: "page 1",
  score: 0.5,
};

describe("transcript helpers", () => {
  it("appendUserTurn appends a sent user turn", () => {
    const out = appendUserTurn([], "hi");
    expect(out).toHaveLength(1);
    const t = out[0] as Turn;
    expect(t.role).toBe("user");
    expect(t.content).toBe("hi");
    expect(t.state).toBe("sent");
  });

  it("startAssistantTurn appends an empty streaming assistant turn", () => {
    const out = startAssistantTurn([]);
    const t = out[0] as Turn;
    expect(t.role).toBe("assistant");
    expect(t.state).toBe("streaming");
    expect(t.content).toBe("");
  });

  it("appendTokenInPlace mutates the trailing assistant turn", () => {
    const seeded = startAssistantTurn([]);
    const sameRef = appendTokenInPlace(seeded, "abc");
    expect(sameRef).toBe(seeded); // same array reference
    expect(seeded[0]?.content).toBe("abc");
    appendTokenInPlace(seeded, "def");
    expect(seeded[0]?.content).toBe("abcdef");
  });

  it("appendTokenInPlace creates an assistant turn when none trails", () => {
    const start = appendUserTurn([], "q");
    const out = appendTokenInPlace(start, "ans");
    expect(out).toHaveLength(2);
    expect(out[1]?.role).toBe("assistant");
    expect(out[1]?.content).toBe("ans");
  });

  it("setCitations replaces the trailing turn's citations", () => {
    const seeded = startAssistantTurn([]);
    const updated = setCitations(seeded, [cit]);
    expect(updated[0]?.citations).toEqual([cit]);
    // returns a NEW array — copy-on-write
    expect(updated).not.toBe(seeded);
  });

  it("finalizeTrailingTurn marks state + carries new turn id", () => {
    const seeded = startAssistantTurn([]);
    const out = finalizeTrailingTurn(seeded, "complete", "turn-final");
    expect(out[0]?.state).toBe("complete");
    expect(out[0]?.id).toBe("turn-final");
  });
});
