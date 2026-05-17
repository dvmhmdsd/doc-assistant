import { useCallback, useReducer, useRef } from "react";

import { uploadDocument } from "./api/upload";
import { ApiError } from "./api/client";
import { UploadSurface, type UploadSurfaceState } from "./components/UploadSurface";
import { documentMetaFromUploadResponse, sessionReducer, type SessionState } from "./state/session";
import { saveSession } from "./state/persistence";

const INITIAL_STATE: SessionState = { kind: "empty" };

function uploadSurfaceStateFrom(state: SessionState): UploadSurfaceState {
  switch (state.kind) {
    case "empty":
      return { kind: "empty" };
    case "uploading":
      return { kind: "uploading", filename: state.filename, progress: state.progress };
    case "ready":
    case "streaming":
      return { kind: "ready", filename: state.document.filename };
    case "error":
      return { kind: "error", message: state.message };
  }
}

export default function App(): React.ReactElement {
  const [state, dispatch] = useReducer(sessionReducer, INITIAL_STATE);
  const abortRef = useRef<AbortController | null>(null);

  const onSelect = useCallback(async (file: File): Promise<void> => {
    dispatch({ type: "uploadStarted", filename: file.name });
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const resp = await uploadDocument(
        file,
        null,
        (loaded, total) => {
          const pct = total > 0 ? Math.round((loaded / total) * 100) : 0;
          dispatch({ type: "uploadProgress", progress: pct });
        },
        controller.signal,
      );
      saveSession(resp.session_id);
      dispatch({
        type: "uploadSucceeded",
        response: {
          sessionId: resp.session_id,
          document: documentMetaFromUploadResponse(resp),
        },
      });
    } catch (err) {
      let message = "Upload failed.";
      if (err instanceof ApiError || err instanceof Error) message = err.message;
      dispatch({ type: "uploadFailed", message });
    } finally {
      abortRef.current = null;
    }
  }, []);

  const onValidationError = useCallback((message: string): void => {
    dispatch({ type: "uploadStarted", filename: "" });
    dispatch({ type: "uploadFailed", message });
  }, []);

  return (
    <main className="min-h-screen bg-neutral-950 p-6 text-neutral-100">
      <div className="mx-auto flex max-w-3xl flex-col gap-6">
        <header>
          <h1 className="text-2xl font-semibold">Doc Assistant</h1>
          <p className="text-sm text-neutral-400">
            Upload a document, then ask questions about it.
          </p>
        </header>

        <UploadSurface
          state={uploadSurfaceStateFrom(state)}
          onSelect={(file) => void onSelect(file)}
          onValidationError={onValidationError}
        />
      </div>
    </main>
  );
}
