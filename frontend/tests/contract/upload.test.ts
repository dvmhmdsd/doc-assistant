import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../src/api/client";
import { uploadDocument } from "../../src/api/upload";
import { ErrorCodeEnum } from "../../src/api/generated";
import type { Error as ApiErrorBody, UploadResponse } from "../../src/api/generated";

/**
 * Contract test for POST /upload.
 *
 * `uploadDocument` uses `XMLHttpRequest` (only browser API exposing upload
 * progress events). MSW v2's XHR interceptor collides with jsdom's built-in
 * `XMLHttpRequest`, so we stub `XMLHttpRequest` directly and assert on the
 * captured request + simulated responses. This keeps the test deterministic
 * and lets us verify FR-024 (no Authorization header) without relying on
 * fetch interception.
 */

type Headers = Record<string, string>;

class FakeXHR {
  status = 0;
  statusText = "";
  responseType: XMLHttpRequestResponseType = "";
  response: unknown = null;
  onload: ((this: XMLHttpRequest, ev: ProgressEvent) => void) | null = null;
  onerror: ((this: XMLHttpRequest, ev: ProgressEvent) => void) | null = null;
  onabort: ((this: XMLHttpRequest, ev: ProgressEvent) => void) | null = null;
  upload = { onprogress: null as ((ev: ProgressEvent) => void) | null };
  private url = "";
  private method = "";
  private headers: Headers = {};
  private body: BodyInit | null = null;

  static readonly instances: FakeXHR[] = [];

  static reset(): void {
    FakeXHR.instances.length = 0;
  }

  constructor() {
    FakeXHR.instances.push(this);
  }

  open(method: string, url: string): void {
    this.method = method;
    this.url = url;
  }

  setRequestHeader(name: string, value: string): void {
    this.headers[name] = value;
  }

  send(body?: BodyInit | null): void {
    this.body = body ?? null;
  }

  abort(): void {
    this.onabort?.call(this as unknown as XMLHttpRequest, new ProgressEvent("abort"));
  }

  // Test helpers — not real XHR API.
  _capture(): { method: string; url: string; headers: Headers; body: BodyInit | null } {
    return { method: this.method, url: this.url, headers: this.headers, body: this.body };
  }

  _resolve(status: number, responseBody: unknown): void {
    this.status = status;
    this.statusText = status === 200 ? "OK" : "Error";
    this.response = responseBody;
    this.onload?.call(this as unknown as XMLHttpRequest, new ProgressEvent("load"));
  }
}

beforeEach(() => {
  FakeXHR.reset();
  vi.stubGlobal("XMLHttpRequest", FakeXHR as unknown as typeof XMLHttpRequest);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function makePdf(name = "paper.pdf"): File {
  return new File([new Uint8Array(8)], name, { type: "application/pdf" });
}

const UPLOAD_OK: UploadResponse = {
  session_id: "sid-1",
  document_id: "doc-1",
  filename: "paper.pdf",
  mime_type: "application/pdf",
  byte_size: 8,
  page_count: 1,
  chunk_count: 2,
  ingested_at: "2026-05-17T00:00:00.000Z",
};

describe("POST /upload contract", () => {
  it("returns the typed UploadResponse on 200", async () => {
    const controller = new AbortController();
    const promise = uploadDocument(makePdf(), null, vi.fn(), controller.signal);
    const xhr = FakeXHR.instances[0];
    expect(xhr).toBeDefined();
    xhr!._resolve(200, UPLOAD_OK);
    await expect(promise).resolves.toEqual(UPLOAD_OK);
  });

  it("sends a multipart/form-data body and never attaches Authorization (FR-024)", async () => {
    const controller = new AbortController();
    const promise = uploadDocument(makePdf(), null, vi.fn(), controller.signal);
    const xhr = FakeXHR.instances[0]!;
    const captured = xhr._capture();

    expect(captured.method).toBe("POST");
    expect(captured.url).toBe("/upload");
    expect(captured.body).toBeInstanceOf(FormData);
    expect((captured.body as FormData).get("file")).toBeInstanceOf(File);

    // Critical regression guard: no Authorization header, ever.
    const headerNames = Object.keys(captured.headers).map((h) => h.toLowerCase());
    expect(headerNames).not.toContain("authorization");

    xhr._resolve(200, UPLOAD_OK);
    await promise;
  });

  it("adds X-Session-Id header iff sessionId provided", async () => {
    const controller = new AbortController();
    const promise = uploadDocument(makePdf(), "sid-existing", vi.fn(), controller.signal);
    const xhr = FakeXHR.instances[0]!;
    expect(xhr._capture().headers["X-Session-Id"]).toBe("sid-existing");
    xhr._resolve(200, UPLOAD_OK);
    await promise;
  });

  it("surfaces the verbatim Error.message on 413", async () => {
    const body: ApiErrorBody = {
      code: ErrorCodeEnum.PayloadTooLarge,
      message: "File too large (max 25 MB)",
    };
    const controller = new AbortController();
    const promise = uploadDocument(makePdf(), null, vi.fn(), controller.signal);
    FakeXHR.instances[0]!._resolve(413, body);
    await expect(promise).rejects.toMatchObject({
      message: "File too large (max 25 MB)",
      status: 413,
    });
  });

  it("surfaces the verbatim Error.message on 415", async () => {
    const body: ApiErrorBody = {
      code: ErrorCodeEnum.UnsupportedMediaType,
      message: "Only PDF or DOCX",
    };
    const controller = new AbortController();
    const promise = uploadDocument(makePdf(), null, vi.fn(), controller.signal);
    FakeXHR.instances[0]!._resolve(415, body);
    await expect(promise).rejects.toMatchObject({ message: "Only PDF or DOCX", status: 415 });
  });

  it("surfaces the verbatim Error.message on 400", async () => {
    const body: ApiErrorBody = {
      code: ErrorCodeEnum.BadRequest,
      message: "Malformed multipart body",
    };
    const controller = new AbortController();
    const promise = uploadDocument(makePdf(), null, vi.fn(), controller.signal);
    FakeXHR.instances[0]!._resolve(400, body);
    await expect(promise).rejects.toBeInstanceOf(ApiError);
    await expect(promise).rejects.toMatchObject({ message: "Malformed multipart body" });
  });
});
