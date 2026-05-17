import type { DocumentMeta } from "./session";

const KEY = "doc-assistant.session";

export type PersistedSession = {
  sessionId: string;
  document: DocumentMeta;
};

function readRaw(): string | null {
  try {
    return sessionStorage.getItem(KEY);
  } catch {
    // sandboxed iframes raise SecurityError on access
    return null;
  }
}

/**
 * Returns the persisted session payload, or `null` when nothing is
 * persisted / storage is inaccessible / the payload is malformed.
 *
 * `null` covers two distinct cases on purpose: legitimately empty
 * (first visit) and corrupted (older schema, partial write). Treating
 * them identically lets the caller fall back to the empty state in
 * both. We deliberately do NOT log corrupted entries — there is no
 * actionable signal and the payload could contain a session_id we
 * should not log per FR-024.
 */
export function loadSession(): PersistedSession | null {
  const raw = readRaw();
  if (raw === null) return null;
  // Legacy: the v1 of this code stored the bare session_id string.
  // Treat that as "incompatible payload → empty state" rather than
  // attempting partial rehydration with a synthetic document.
  if (!raw.startsWith("{")) return null;
  try {
    const parsed = JSON.parse(raw) as Partial<PersistedSession> | null;
    if (
      parsed === null ||
      typeof parsed.sessionId !== "string" ||
      typeof parsed.document !== "object" ||
      parsed.document === null
    ) {
      return null;
    }
    return parsed as PersistedSession;
  } catch {
    return null;
  }
}

export function saveSession(payload: PersistedSession): void {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(payload));
  } catch {
    // swallow SecurityError
  }
}

export function clearSession(): void {
  try {
    sessionStorage.removeItem(KEY);
  } catch {
    // swallow SecurityError
  }
}
