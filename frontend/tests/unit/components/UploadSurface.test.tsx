import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { UploadSurface } from "../../../src/components/UploadSurface";

function fireFileSelect(input: HTMLInputElement, file: File): void {
  Object.defineProperty(input, "files", { value: [file], configurable: true });
  fireEvent.change(input);
}

const MAX_BYTES = 25 * 1024 * 1024;

function makeFile(name: string, sizeBytes: number, type = "application/pdf"): File {
  const buf = new Uint8Array(Math.min(sizeBytes, 16));
  const file = new File([buf], name, { type });
  // jsdom respects File.size from blob bits; override for oversize tests.
  Object.defineProperty(file, "size", { value: sizeBytes });
  return file;
}

describe("UploadSurface", () => {
  it("renders an idle drop zone in the empty state", () => {
    render(
      <UploadSurface
        state={{ kind: "empty" }}
        onSelect={vi.fn()}
        onValidationError={vi.fn()}
      />,
    );

    expect(screen.getByRole("region", { name: /upload/i })).toBeInTheDocument();
    expect(screen.getByText(/drag and drop/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /choose a file/i })).toBeInTheDocument();
  });

  it("shows a drag-over visual cue while a file is being dragged", () => {
    render(
      <UploadSurface
        state={{ kind: "empty" }}
        onSelect={vi.fn()}
        onValidationError={vi.fn()}
      />,
    );
    const zone = screen.getByTestId("upload-dropzone");
    fireEvent.dragEnter(zone);
    expect(zone).toHaveAttribute("data-dragging", "true");
    fireEvent.dragLeave(zone);
    expect(zone).toHaveAttribute("data-dragging", "false");
  });

  it("rejects .txt files client-side and never calls onSelect (FR-004)", () => {
    const onSelect = vi.fn();
    const onValidationError = vi.fn();
    render(
      <UploadSurface
        state={{ kind: "empty" }}
        onSelect={onSelect}
        onValidationError={onValidationError}
      />,
    );

    const input = screen.getByTestId("upload-input") as HTMLInputElement;
    fireFileSelect(input, makeFile("notes.txt", 1024, "text/plain"));

    expect(onSelect).not.toHaveBeenCalled();
    expect(onValidationError).toHaveBeenCalledTimes(1);
    expect(onValidationError.mock.calls[0]?.[0]).toMatch(/pdf.*docx/i);
  });

  it("rejects files larger than 25 MB client-side (FR-004)", () => {
    const onSelect = vi.fn();
    const onValidationError = vi.fn();
    render(
      <UploadSurface
        state={{ kind: "empty" }}
        onSelect={onSelect}
        onValidationError={onValidationError}
      />,
    );

    const input = screen.getByTestId("upload-input") as HTMLInputElement;
    fireFileSelect(input, makeFile("huge.pdf", MAX_BYTES + 1, "application/pdf"));

    expect(onSelect).not.toHaveBeenCalled();
    expect(onValidationError).toHaveBeenCalledTimes(1);
    expect(onValidationError.mock.calls[0]?.[0]).toMatch(/25/);
  });

  it("accepts a valid .pdf under 25 MB and calls onSelect", async () => {
    const onSelect = vi.fn();
    const onValidationError = vi.fn();
    const user = userEvent.setup();
    render(
      <UploadSurface
        state={{ kind: "empty" }}
        onSelect={onSelect}
        onValidationError={onValidationError}
      />,
    );

    const file = makeFile("paper.pdf", 1024, "application/pdf");
    const input = screen.getByTestId("upload-input") as HTMLInputElement;
    await user.upload(input, file);

    expect(onValidationError).not.toHaveBeenCalled();
    expect(onSelect).toHaveBeenCalledWith(file);
  });

  it("shows a progress indicator during uploading", () => {
    render(
      <UploadSurface
        state={{ kind: "uploading", filename: "paper.pdf", progress: 42 }}
        onSelect={vi.fn()}
        onValidationError={vi.fn()}
      />,
    );

    const progress = screen.getByRole("progressbar");
    expect(progress).toBeInTheDocument();
    expect(progress).toHaveAttribute("aria-valuenow", "42");
    expect(screen.getByText(/paper\.pdf/)).toBeInTheDocument();
  });

  it("announces the ready state via aria-live (FR-002, FR-016)", () => {
    render(
      <UploadSurface
        state={{ kind: "ready", filename: "paper.pdf" }}
        onSelect={vi.fn()}
        onValidationError={vi.fn()}
      />,
    );

    const status = screen.getByTestId("upload-status");
    expect(status).toHaveAttribute("aria-live", "polite");
    expect(status).toHaveTextContent(/ready/i);
    expect(status).toHaveTextContent(/paper\.pdf/);
  });

  it("renders an inline error band with the verbatim message (FR-013) and no popup", () => {
    render(
      <UploadSurface
        state={{ kind: "error", message: "File too large (max 25 MB)" }}
        onSelect={vi.fn()}
        onValidationError={vi.fn()}
      />,
    );

    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    const error = screen.getByRole("alert");
    expect(error).toHaveTextContent("File too large (max 25 MB)");
  });
});
