import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { Transcript } from "../../../src/components/Transcript";
import type { Turn } from "../../../src/state/transcript";

function turn(role: Turn["role"], content: string, id: string): Turn {
  return {
    id,
    role,
    content,
    citations: null,
    state: "complete",
    createdAt: "2026-05-17T00:00:00.000Z",
  };
}

describe("Transcript — multi-turn rendering (US3)", () => {
  it("renders 20 turns in order without ARIA id collisions", () => {
    const turns: Turn[] = [];
    for (let i = 0; i < 10; i += 1) {
      turns.push(turn("user", `q${i}`, `u-${i}`));
      turns.push(turn("assistant", `a${i}`, `a-${i}`));
    }
    render(<Transcript turns={turns} />);
    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(20);
    items.forEach((el, idx) => {
      const expectedRole = idx % 2 === 0 ? "user" : "assistant";
      expect(el).toHaveAttribute("data-role", expectedRole);
    });
  });

  it("preserves chronological order even when ids are unrelated to position", () => {
    const turns: Turn[] = [
      turn("user", "q1", "z-99"),
      turn("assistant", "a1", "a-00"),
      turn("user", "q2", "m-50"),
      turn("assistant", "a2", "n-49"),
    ];
    render(<Transcript turns={turns} />);
    const items = screen.getAllByRole("listitem");
    expect(items[0]?.textContent).toContain("q1");
    expect(items[1]?.textContent).toContain("a1");
    expect(items[2]?.textContent).toContain("q2");
    expect(items[3]?.textContent).toContain("a2");
  });
});
