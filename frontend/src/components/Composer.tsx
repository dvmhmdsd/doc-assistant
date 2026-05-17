import { useState, type KeyboardEvent } from "react";

const MAX_LEN = 4000;

type Props = {
  disabled: boolean;
  streaming: boolean;
  onSubmit: (text: string) => void;
  onCancel: () => void;
};

export function Composer({
  disabled,
  streaming,
  onSubmit,
  onCancel,
}: Props): React.ReactElement {
  const [text, setText] = useState("");

  const trySubmit = (): void => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSubmit(trimmed);
    setText("");
  };

  const handleSubmit = (ev: { preventDefault: () => void }): void => {
    ev.preventDefault();
    trySubmit();
  };

  const handleKeyDown = (ev: KeyboardEvent<HTMLTextAreaElement>): void => {
    if (ev.key === "Enter" && !ev.shiftKey) {
      ev.preventDefault();
      trySubmit();
      return;
    }
    if (ev.key === "Escape" && streaming) {
      ev.preventDefault();
      onCancel();
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-2 border-t border-neutral-800 pt-3">
      <textarea
        aria-label="Question"
        placeholder={disabled ? "Answering…" : "Ask a question about the document"}
        value={text}
        maxLength={MAX_LEN}
        disabled={disabled}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        rows={2}
        className="w-full resize-none rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-neutral-100 placeholder:text-neutral-500 focus-visible:ring-2 focus-visible:ring-blue-400 disabled:opacity-60"
      />
      <div className="flex items-center justify-between text-xs text-neutral-400">
        <span data-testid="composer-status">
          {disabled
            ? streaming
              ? "Answering…"
              : "Working…"
            : `${text.length}/${MAX_LEN}`}
        </span>
        <div className="flex gap-2">
          {streaming ? (
            <button
              type="button"
              onClick={onCancel}
              className="rounded bg-red-700/70 px-3 py-1 text-white hover:bg-red-700 focus-visible:ring-2 focus-visible:ring-red-300"
            >
              Cancel
            </button>
          ) : (
            <button
              type="submit"
              disabled={disabled || text.trim().length === 0}
              className="rounded bg-blue-600 px-3 py-1 text-white hover:bg-blue-500 focus-visible:ring-2 focus-visible:ring-blue-300 disabled:opacity-50"
            >
              Send
            </button>
          )}
        </div>
      </div>
    </form>
  );
}
