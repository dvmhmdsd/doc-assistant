const KEY = "doc-assistant.session";

export function loadSession(): string | null {
  try {
    return sessionStorage.getItem(KEY);
  } catch {
    // sandboxed iframes raise SecurityError on access
    return null;
  }
}

export function saveSession(sessionId: string): void {
  try {
    sessionStorage.setItem(KEY, sessionId);
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
