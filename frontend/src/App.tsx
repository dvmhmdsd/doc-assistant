import { useCallback, useEffect, useReducer } from "react";

import { streamAnswer } from "./api/ask";
import { ApiError } from "./api/client";
import { fetchHistory } from "./api/history";
import { uploadDocument } from "./api/upload";
import { Composer } from "./components/Composer";
import { Transcript } from "./components/Transcript";
import { UploadSurface, type UploadSurfaceState } from "./components/UploadSurface";
import { clearSession, loadSession, saveSession } from "./state/persistence";
import {
  documentMetaFromUploadResponse,
  sessionReducer,
  type SessionState,
} from "./state/session";
import type { Turn } from "./state/transcript";

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

  useEffect(() => {
    // US3 rehydration: pick up the previously-persisted session on mount.
    const persisted = loadSession();
    if (persisted === null) return;
    let cancelled = false;
    (async () => {
      try {
        const resp = await fetchHistory(persisted.sessionId);
        if (cancelled) return;
        const transcript: Turn[] = resp.turns.map((t) => ({
          id: t.turn_id,
          role: t.role,
          content: t.content,
          citations: t.citations ?? null,
          state: t.state ?? "complete",
          createdAt: t.created_at,
        }));
        dispatch({
          type: "rehydrated",
          response: {
            sessionId: persisted.sessionId,
            document: persisted.document,
            transcript,
          },
        });
      } catch {
        if (cancelled) return;
        clearSession();
        dispatch({ type: "rehydrateFailed" });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const onSelect = useCallback(async (file: File): Promise<void> => {
    dispatch({ type: "uploadStarted", filename: file.name });
    const controller = new AbortController();
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
      const document = documentMetaFromUploadResponse(resp);
      saveSession({ sessionId: resp.session_id, document });
      dispatch({
        type: "uploadSucceeded",
        response: { sessionId: resp.session_id, document },
      });
    } catch (err) {
      let message = "Upload failed.";
      if (err instanceof ApiError || err instanceof Error) message = err.message;
      dispatch({ type: "uploadFailed", message });
    }
  }, []);

  const onValidationError = useCallback((message: string): void => {
    dispatch({ type: "uploadStarted", filename: "" });
    dispatch({ type: "uploadFailed", message });
  }, []);

  const onAsk = useCallback(
    async (text: string): Promise<void> => {
      if (state.kind !== "ready") return;
      const sessionId = state.sessionId;
      const controller = new AbortController();
      dispatch({ type: "submitQuestion", text, controller });
      try {
        await streamAnswer(
          { session_id: sessionId, question: text },
          (e) => {
            switch (e.type) {
              case "token":
                dispatch({ type: "tokenAppended", text: e.text });
                return;
              case "citations":
                dispatch({ type: "citationsReceived", citations: e.citations });
                return;
              case "done":
                dispatch({ type: "streamDone", turnId: e.turn_id, stopped: e.stopped });
                return;
              case "error":
                dispatch({ type: "streamErrored", message: e.message });
                return;
            }
          },
          controller.signal,
        );
      } catch (err) {
        if (controller.signal.aborted) return;
        let message = "Streaming failed.";
        if (err instanceof ApiError || err instanceof Error) message = err.message;
        dispatch({ type: "streamErrored", message });
      }
    },
    [state],
  );

  const onCancel = useCallback((): void => {
    if (state.kind !== "streaming") return;
    state.controller.abort();
    dispatch({ type: "streamCancelled" });
  }, [state]);

  const isReady = state.kind === "ready";
  const isStreaming = state.kind === "streaming";
  const transcript =
    state.kind === "ready" || state.kind === "streaming" ? state.transcript : [];

  return (
    <main className="min-h-screen bg-neutral-950 p-4 text-neutral-100 md:p-6">
      <div className="mx-auto flex h-[calc(100vh-2rem)] max-w-3xl flex-col gap-4 md:h-[calc(100vh-3rem)]">
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

        {(isReady || isStreaming) && (
          <>
            <Transcript turns={transcript} />
            <Composer
              disabled={!isReady}
              streaming={isStreaming}
              onSubmit={(text) => void onAsk(text)}
              onCancel={onCancel}
            />
          </>
        )}
      </div>
    </main>
  );
}
