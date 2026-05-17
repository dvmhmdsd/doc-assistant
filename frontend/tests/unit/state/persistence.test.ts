import { beforeEach, describe, expect, it } from "vitest";

import { clearSession, loadSession, saveSession } from "../../../src/state/persistence";

beforeEach(() => sessionStorage.clear());

describe("persistence (sessionStorage)", () => {
  it("returns null when nothing is stored", () => {
    expect(loadSession()).toBeNull();
  });

  it("round-trips the session id as a raw string", () => {
    saveSession("sid-xyz");
    expect(sessionStorage.getItem("doc-assistant.session")).toBe("sid-xyz");
    expect(loadSession()).toBe("sid-xyz");
  });

  it("clears the stored handle", () => {
    saveSession("sid-xyz");
    clearSession();
    expect(loadSession()).toBeNull();
  });
});
