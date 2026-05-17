import type { Error as ApiErrorBody } from "./generated";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string | undefined;
  readonly requestId: string | undefined;

  constructor(message: string, status: number, code?: string, requestId?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
  }
}

function isJsonContent(contentType: string | null): boolean {
  return (contentType ?? "").toLowerCase().includes("application/json");
}

function isApiErrorBody(body: unknown): body is ApiErrorBody {
  return (
    typeof body === "object" &&
    body !== null &&
    typeof (body as { message?: unknown }).message === "string"
  );
}

export async function fetchJson<T>(input: RequestInfo, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (!headers.has("Accept")) headers.set("Accept", "application/json");
  if (init.body !== undefined && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(input, { ...init, headers });

  if (!res.ok) {
    let body: unknown = null;
    try {
      body = isJsonContent(res.headers.get("content-type"))
        ? await res.json()
        : await res.text();
    } catch {
      body = null;
    }
    if (isApiErrorBody(body)) {
      throw new ApiError(body.message, res.status, body.code, body.request_id);
    }
    throw new ApiError(
      typeof body === "string" && body.length > 0 ? body : res.statusText,
      res.status,
    );
  }

  if (!isJsonContent(res.headers.get("content-type"))) {
    throw new ApiError("Expected JSON response", res.status);
  }
  return (await res.json()) as T;
}
