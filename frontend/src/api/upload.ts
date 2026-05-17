import type { Error as ApiErrorBody, UploadResponse } from "./generated";
import { ApiError } from "./client";

export function uploadDocument(
  file: File,
  sessionId: string | null,
  onProgress: (loaded: number, total: number) => void,
  signal: AbortSignal,
): Promise<UploadResponse> {
  return new Promise<UploadResponse>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const form = new FormData();
    form.append("file", file);

    xhr.open("POST", "/upload");
    xhr.setRequestHeader("Accept", "application/json");
    if (sessionId) xhr.setRequestHeader("X-Session-Id", sessionId);
    xhr.responseType = "json";

    xhr.upload.onprogress = (ev: ProgressEvent) => {
      if (ev.lengthComputable) onProgress(ev.loaded, ev.total);
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(xhr.response as UploadResponse);
        return;
      }
      const body = xhr.response as ApiErrorBody | null;
      const message = body?.message ?? xhr.statusText ?? `HTTP ${xhr.status}`;
      reject(new ApiError(message, xhr.status, body?.code, body?.request_id));
    };

    xhr.onerror = () => reject(new ApiError("Network error", 0));
    xhr.onabort = () => reject(new DOMException("Aborted", "AbortError"));

    if (signal.aborted) {
      xhr.abort();
      return;
    }
    signal.addEventListener("abort", () => xhr.abort(), { once: true });

    xhr.send(form);
  });
}
