import { describe } from "vitest";

/**
 * `uploadDocument` uses `XMLHttpRequest` for upload progress events
 * (the only browser API that exposes them). MSW v2's `setupServer`
 * intercepts `fetch` reliably in vitest's jsdom env but its XHR
 * interceptor collides with jsdom's built-in XHR — overridden routes
 * never reach the handler and the underlying `XHR.send` hangs.
 *
 * Until the upload-route contract test (T027) introduces a dedicated
 * XHR test harness (custom `global.XMLHttpRequest` stub or
 * `@mswjs/interceptors` direct integration), the upload happy-path is
 * covered manually via the end-to-end docker compose run in T071.
 */
describe.todo("uploadDocument (XHR + MSW interop pending — see T027)");
