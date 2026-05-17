import type { Citation, UploadResponse } from "../api/generated";
import {
  appendTokenInPlace,
  appendUserTurn,
  finalizeTrailingTurn,
  setCitations,
  type Turn,
} from "./transcript";

export type DocumentMeta = {
  documentId: string;
  filename: string;
  byteSize: number;
  chunkCount: number;
  pageCount: number | null;
  ingestedAt: string;
};

export type SessionState =
  | { kind: "empty" }
  | { kind: "uploading"; filename: string; progress: number }
  | { kind: "ready"; sessionId: string; document: DocumentMeta; transcript: Turn[] }
  | {
      kind: "streaming";
      sessionId: string;
      document: DocumentMeta;
      transcript: Turn[];
      controller: AbortController;
    }
  | { kind: "error"; message: string; previous: SessionState };

export type Action =
  | { type: "uploadStarted"; filename: string }
  | { type: "uploadProgress"; progress: number }
  | { type: "uploadSucceeded"; response: { sessionId: string; document: DocumentMeta } }
  | { type: "uploadFailed"; message: string }
  | {
      type: "rehydrated";
      response: { sessionId: string; document: DocumentMeta; transcript: Turn[] };
    }
  | { type: "rehydrateFailed" }
  | { type: "submitQuestion"; text: string; controller: AbortController }
  | { type: "tokenAppended"; text: string }
  | { type: "citationsReceived"; citations: Citation[] }
  | { type: "streamDone"; turnId: string; stopped: boolean }
  | { type: "streamCancelled" }
  | { type: "streamErrored"; message: string }
  | { type: "retry" }
  | { type: "newSession" };

export function documentMetaFromUploadResponse(resp: UploadResponse): DocumentMeta {
  return {
    documentId: resp.document_id,
    filename: resp.filename,
    byteSize: resp.byte_size,
    chunkCount: resp.chunk_count,
    pageCount: resp.page_count ?? null,
    ingestedAt: resp.ingested_at,
  };
}

function warnInvalidTransition(action: Action["type"], state: SessionState["kind"]): void {
  console.warn(`[session] action "${action}" ignored in state "${state}"`);
}

export function sessionReducer(state: SessionState, action: Action): SessionState {
  switch (action.type) {
    case "uploadStarted": {
      if (state.kind !== "empty") {
        warnInvalidTransition(action.type, state.kind);
        return state;
      }
      return { kind: "uploading", filename: action.filename, progress: 0 };
    }

    case "uploadProgress": {
      if (state.kind !== "uploading") {
        warnInvalidTransition(action.type, state.kind);
        return state;
      }
      return { ...state, progress: action.progress };
    }

    case "uploadSucceeded": {
      if (state.kind !== "uploading") {
        warnInvalidTransition(action.type, state.kind);
        return state;
      }
      return {
        kind: "ready",
        sessionId: action.response.sessionId,
        document: action.response.document,
        transcript: [],
      };
    }

    case "uploadFailed": {
      if (state.kind !== "uploading") {
        warnInvalidTransition(action.type, state.kind);
        return state;
      }
      return { kind: "error", message: action.message, previous: { kind: "empty" } };
    }

    case "rehydrated": {
      return {
        kind: "ready",
        sessionId: action.response.sessionId,
        document: action.response.document,
        transcript: action.response.transcript,
      };
    }

    case "rehydrateFailed": {
      return { kind: "empty" };
    }

    case "submitQuestion": {
      if (state.kind !== "ready") {
        warnInvalidTransition(action.type, state.kind);
        return state;
      }
      return {
        kind: "streaming",
        sessionId: state.sessionId,
        document: state.document,
        transcript: appendUserTurn(state.transcript, action.text),
        controller: action.controller,
      };
    }

    case "tokenAppended": {
      if (state.kind !== "streaming") {
        warnInvalidTransition(action.type, state.kind);
        return state;
      }
      // appendTokenInPlace mutates trailing turn's content for streaming
      // perf; the reducer still returns the same state ref so React skips
      // a transcript-level re-render. Components must observe the trailing
      // turn via a DOM ref (T040) for the user-visible repaint.
      appendTokenInPlace(state.transcript, action.text);
      return state;
    }

    case "citationsReceived": {
      if (state.kind !== "streaming") {
        warnInvalidTransition(action.type, state.kind);
        return state;
      }
      return { ...state, transcript: setCitations(state.transcript, action.citations) };
    }

    case "streamDone": {
      if (state.kind !== "streaming") {
        warnInvalidTransition(action.type, state.kind);
        return state;
      }
      return {
        kind: "ready",
        sessionId: state.sessionId,
        document: state.document,
        transcript: finalizeTrailingTurn(
          state.transcript,
          action.stopped ? "stopped" : "complete",
          action.turnId,
        ),
      };
    }

    case "streamCancelled": {
      if (state.kind !== "streaming") {
        warnInvalidTransition(action.type, state.kind);
        return state;
      }
      return {
        kind: "ready",
        sessionId: state.sessionId,
        document: state.document,
        transcript: finalizeTrailingTurn(state.transcript, "stopped"),
      };
    }

    case "streamErrored": {
      if (state.kind !== "streaming") {
        warnInvalidTransition(action.type, state.kind);
        return state;
      }
      const previous: SessionState = {
        kind: "ready",
        sessionId: state.sessionId,
        document: state.document,
        transcript: finalizeTrailingTurn(state.transcript, "errored"),
      };
      return { kind: "error", message: action.message, previous };
    }

    case "retry": {
      if (state.kind !== "error") {
        warnInvalidTransition(action.type, state.kind);
        return state;
      }
      return state.previous;
    }

    case "newSession": {
      return { kind: "empty" };
    }

    default: {
      const exhaustive: never = action;
      throw new Error(`Unhandled action: ${JSON.stringify(exhaustive)}`);
    }
  }
}
