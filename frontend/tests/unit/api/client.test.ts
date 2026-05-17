import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { ApiError, fetchJson } from "../../../src/api/client";
import { server } from "../../mocks/server";

describe("fetchJson", () => {
  it("returns parsed JSON for 2xx with application/json", async () => {
    server.use(
      http.get("/api/widget", () =>
        HttpResponse.json({ ok: true, value: 42 }, { status: 200 }),
      ),
    );

    const out = await fetchJson<{ ok: boolean; value: number }>("/api/widget");

    expect(out).toEqual({ ok: true, value: 42 });
  });

  it("sets Accept: application/json by default", async () => {
    let captured: string | null = null;
    server.use(
      http.get("/api/echo-accept", ({ request }) => {
        captured = request.headers.get("accept");
        return HttpResponse.json({});
      }),
    );

    await fetchJson("/api/echo-accept");

    expect(captured).toContain("application/json");
  });

  it("sets Content-Type: application/json on non-FormData bodies", async () => {
    let captured: string | null = null;
    server.use(
      http.post("/api/echo-ct", async ({ request }) => {
        captured = request.headers.get("content-type");
        return HttpResponse.json({});
      }),
    );

    await fetchJson("/api/echo-ct", {
      method: "POST",
      body: JSON.stringify({ x: 1 }),
    });

    expect(captured).toContain("application/json");
  });

  it("does NOT overwrite Content-Type for FormData bodies", async () => {
    let captured: string | null = null;
    server.use(
      http.post("/api/echo-ct-form", async ({ request }) => {
        captured = request.headers.get("content-type");
        return HttpResponse.json({});
      }),
    );

    const form = new FormData();
    form.append("file", new Blob(["x"]));
    await fetchJson("/api/echo-ct-form", { method: "POST", body: form });

    expect(captured).toContain("multipart/form-data");
  });

  it("never attaches Authorization header", async () => {
    let captured: string | null = "set";
    server.use(
      http.get("/api/echo-auth", ({ request }) => {
        captured = request.headers.get("authorization");
        return HttpResponse.json({});
      }),
    );

    await fetchJson("/api/echo-auth");

    expect(captured).toBeNull();
  });

  it("maps non-2xx JSON error body to ApiError", async () => {
    server.use(
      http.get("/api/broken", () =>
        HttpResponse.json(
          { code: "bad_request", message: "nope", request_id: "rid-1" },
          { status: 400 },
        ),
      ),
    );

    await expect(fetchJson("/api/broken")).rejects.toMatchObject({
      name: "ApiError",
      status: 400,
      code: "bad_request",
      requestId: "rid-1",
      message: "nope",
    });
  });

  it("throws ApiError when response is non-JSON for a 2xx", async () => {
    server.use(
      http.get("/api/html", () =>
        new HttpResponse("<html>", {
          status: 200,
          headers: { "Content-Type": "text/html" },
        }),
      ),
    );

    await expect(fetchJson("/api/html")).rejects.toBeInstanceOf(ApiError);
  });
});
