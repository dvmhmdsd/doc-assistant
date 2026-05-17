import {
  useCallback,
  useId,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
} from "react";
import clsx from "clsx";

const MAX_BYTES = 25 * 1024 * 1024;
const ACCEPTED_EXTS = [".pdf", ".docx"] as const;
const ACCEPT_ATTR = ACCEPTED_EXTS.join(",");

export type UploadSurfaceState =
  | { kind: "empty" }
  | { kind: "uploading"; filename: string; progress: number }
  | { kind: "ready"; filename: string }
  | { kind: "error"; message: string };

export type UploadSurfaceProps = {
  state: UploadSurfaceState;
  onSelect: (file: File) => void;
  onValidationError: (message: string) => void;
};

function validate(file: File): string | null {
  const name = file.name.toLowerCase();
  const ok = ACCEPTED_EXTS.some((ext) => name.endsWith(ext));
  if (!ok) return "Unsupported file type. Upload a .pdf or .docx file.";
  if (file.size > MAX_BYTES) return "File too large. Limit is 25 MB.";
  return null;
}

export function UploadSurface({
  state,
  onSelect,
  onValidationError,
}: UploadSurfaceProps): React.ReactElement {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const headingId = useId();

  const handleFile = useCallback(
    (file: File): void => {
      const err = validate(file);
      if (err) {
        onValidationError(err);
        return;
      }
      onSelect(file);
    },
    [onSelect, onValidationError],
  );

  const onInputChange = (ev: ChangeEvent<HTMLInputElement>): void => {
    const file = ev.target.files?.[0];
    if (file) handleFile(file);
    ev.target.value = "";
  };

  const onDrop = (ev: DragEvent<HTMLDivElement>): void => {
    ev.preventDefault();
    setDragging(false);
    const file = ev.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  const onDragEnter = (ev: DragEvent<HTMLDivElement>): void => {
    ev.preventDefault();
    setDragging(true);
  };
  const onDragOver = (ev: DragEvent<HTMLDivElement>): void => {
    ev.preventDefault();
  };
  const onDragLeave = (): void => setDragging(false);

  const openPicker = (): void => inputRef.current?.click();
  const interactive = state.kind === "empty";

  return (
    <section
      aria-labelledby={headingId}
      className="w-full rounded-lg border border-neutral-700 bg-neutral-900/40 p-6"
    >
      <h2 id={headingId} className="sr-only">
        Upload document
      </h2>

      <div
        data-testid="upload-dropzone"
        data-dragging={dragging ? "true" : "false"}
        onDrop={interactive ? onDrop : undefined}
        onDragEnter={interactive ? onDragEnter : undefined}
        onDragOver={interactive ? onDragOver : undefined}
        onDragLeave={interactive ? onDragLeave : undefined}
        className={clsx(
          "flex flex-col items-center justify-center gap-3 rounded-md border-2 border-dashed p-8 text-center transition-colors",
          dragging
            ? "border-blue-400 bg-blue-400/10"
            : "border-neutral-600 bg-neutral-800/40",
          !interactive && "opacity-80",
        )}
      >
        {state.kind === "empty" && (
          <>
            <p className="text-sm text-neutral-200">
              Drag and drop a PDF or DOCX here, or
            </p>
            <button
              type="button"
              onClick={openPicker}
              className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 focus-visible:ring-2 focus-visible:ring-blue-300"
            >
              Choose a file
            </button>
            <p className="text-xs text-neutral-400">Max 25 MB.</p>
          </>
        )}

        {state.kind === "uploading" && (
          <div className="w-full max-w-md">
            <p className="mb-2 text-sm text-neutral-200">
              Uploading <span className="font-medium">{state.filename}</span>…
            </p>
            <div
              role="progressbar"
              aria-valuenow={state.progress}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label={`Upload progress for ${state.filename}`}
              className="h-2 w-full overflow-hidden rounded bg-neutral-700"
            >
              <div
                className="h-full bg-blue-500 transition-all"
                style={{ width: `${Math.min(100, Math.max(0, state.progress))}%` }}
              />
            </div>
          </div>
        )}

        {state.kind === "ready" && (
          <p
            data-testid="upload-status"
            aria-live="polite"
            className="text-sm text-emerald-300"
          >
            Ready — <span className="font-medium">{state.filename}</span> is loaded.
          </p>
        )}

        {state.kind === "error" && (
          <div role="alert" className="rounded bg-red-900/30 px-3 py-2 text-sm text-red-200">
            {state.message}
          </div>
        )}
      </div>

      <input
        ref={inputRef}
        data-testid="upload-input"
        type="file"
        accept={ACCEPT_ATTR}
        className="hidden"
        onChange={onInputChange}
      />
    </section>
  );
}
