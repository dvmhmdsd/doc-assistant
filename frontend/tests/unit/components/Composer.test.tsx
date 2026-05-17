import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { Composer } from "../../../src/components/Composer";

describe("Composer", () => {
  it("blocks empty / whitespace-only submissions client-side", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();
    render(<Composer disabled={false} onSubmit={onSubmit} onCancel={vi.fn()} streaming={false} />);

    const textarea = screen.getByRole("textbox", { name: /question/i });
    await user.type(textarea, "   ");
    await user.click(screen.getByRole("button", { name: /send/i }));
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits trimmed text on Enter and clears the textarea", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();
    render(<Composer disabled={false} onSubmit={onSubmit} onCancel={vi.fn()} streaming={false} />);

    const textarea = screen.getByRole("textbox", { name: /question/i }) as HTMLTextAreaElement;
    await user.type(textarea, "What is this?{Enter}");
    expect(onSubmit).toHaveBeenCalledWith("What is this?");
    expect(textarea.value).toBe("");
  });

  it("caps input at 4000 characters (matches AskRequest.maxLength)", () => {
    render(<Composer disabled={false} onSubmit={vi.fn()} onCancel={vi.fn()} streaming={false} />);
    const textarea = screen.getByRole("textbox", { name: /question/i }) as HTMLTextAreaElement;
    expect(textarea.maxLength).toBe(4000);
  });

  it("disables textarea + hides send + shows an answering indicator when disabled (FR-012)", () => {
    render(<Composer disabled onSubmit={vi.fn()} onCancel={vi.fn()} streaming />);
    const textarea = screen.getByRole("textbox", { name: /question/i }) as HTMLTextAreaElement;
    expect(textarea.disabled).toBe(true);
    expect(screen.queryByRole("button", { name: /send/i })).toBeNull();
    expect(screen.getByTestId("composer-status")).toHaveTextContent(/answering/i);
  });

  it("renders a cancel button while streaming and Esc triggers it", async () => {
    const onCancel = vi.fn();
    const user = userEvent.setup();
    render(<Composer disabled onSubmit={vi.fn()} onCancel={onCancel} streaming />);

    await user.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onCancel).toHaveBeenCalled();

    // Esc on the textarea triggers cancel too.
    onCancel.mockClear();
    const textarea = screen.getByRole("textbox", { name: /question/i });
    fireEvent.keyDown(textarea, { key: "Escape" });
    expect(onCancel).toHaveBeenCalled();
  });
});
