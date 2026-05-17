import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { Transcript } from "../../../src/components/Transcript";
import type { Turn } from "../../../src/state/transcript";

function turn(role: Turn["role"], content: string, state: Turn["state"] = "complete"): Turn {
  return {
    id: crypto.randomUUID(),
    role,
    content,
    citations: null,
    state,
    createdAt: "2026-05-17T00:00:00.000Z",
  };
}

describe("Transcript", () => {
  it("renders turns inside a <ul role='log'> with aria-live=polite", () => {
    render(<Transcript turns={[turn("user", "hi"), turn("assistant", "hey")]} />);
    const log = screen.getByRole("log");
    expect(log).toHaveAttribute("aria-live", "polite");
    expect(log.tagName).toBe("UL");
  });

  it("marks role on each turn (FR-006)", () => {
    render(<Transcript turns={[turn("user", "hi"), turn("assistant", "hey")]} />);
    const items = screen.getAllByRole("listitem");
    expect(items[0]).toHaveAttribute("data-role", "user");
    expect(items[1]).toHaveAttribute("data-role", "assistant");
  });

  it("exposes data-streaming='true' on a streaming assistant turn", () => {
    render(
      <Transcript turns={[turn("user", "Q"), turn("assistant", "partial", "streaming")]} />,
    );
    const items = screen.getAllByRole("listitem");
    expect(items[1]).toHaveAttribute("data-streaming", "true");
  });

  it("renders 20 turns without overlap (smoke test)", () => {
    const turns: Turn[] = [];
    for (let i = 0; i < 10; i += 1) {
      turns.push(turn("user", `q${i}`));
      turns.push(turn("assistant", `a${i}`));
    }
    render(<Transcript turns={turns} />);
    expect(screen.getAllByRole("listitem")).toHaveLength(20);
  });

  it("renders citations when present on an assistant turn", () => {
    const t = turn("assistant", "ans");
    t.citations = [
      { chunk_id: "c1", document_id: "d1", locator: "p.7", score: 0.91 },
    ];
    render(<Transcript turns={[turn("user", "Q"), t]} />);
    expect(screen.getByText(/p\.7/)).toBeInTheDocument();
  });
});
