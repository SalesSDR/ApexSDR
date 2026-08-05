/**
 * Sprint 7.1: authenticated-fetch client tests. The core Sprint 7.1 finding
 * this covers - several dashboard pages called `fetch()` directly against a
 * duplicated, hardcoded API_BASE_URL and never attached a credential, so
 * every one of those calls 401'd in production. This asserts fetchApi (the
 * one client every page should now use) always attaches the Authorization
 * header when a credential is configured, and never fabricates one when it
 * isn't.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

function freshLocalStorage() {
  const store = new Map<string, string>();
  return {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => {
      store.set(key, value);
    },
    removeItem: (key: string) => {
      store.delete(key);
    },
    clear: () => store.clear(),
  };
}

describe("fetchApi (authenticated API client)", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.resetModules();
    delete process.env.NEXT_PUBLIC_API_CREDENTIAL;
    (globalThis as unknown as { window: unknown }).window = { localStorage: freshLocalStorage() };
    fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: "success" }),
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    delete (globalThis as unknown as { window?: unknown }).window;
  });

  it("attaches no Authorization header when no credential is configured", async () => {
    const { fetchApi } = await import("./api");
    await fetchApi("/prospects");

    const [, options] = fetchMock.mock.calls[0];
    const headers = new Headers(options.headers);
    expect(headers.has("Authorization")).toBe(false);
  });

  it("attaches Authorization: Bearer <credential> once one is stored", async () => {
    const { fetchApi, setAuthCredential } = await import("./api");
    setAuthCredential("a-real-jwt-or-api-key");

    await fetchApi("/prospects");

    const [, options] = fetchMock.mock.calls[0];
    const headers = new Headers(options.headers);
    expect(headers.get("Authorization")).toBe("Bearer a-real-jwt-or-api-key");
  });

  it("prefers the build-time NEXT_PUBLIC_API_CREDENTIAL over localStorage", async () => {
    process.env.NEXT_PUBLIC_API_CREDENTIAL = "build-time-credential";
    const { fetchApi, setAuthCredential } = await import("./api");
    setAuthCredential("stored-credential-should-be-ignored");

    await fetchApi("/prospects");

    const [, options] = fetchMock.mock.calls[0];
    const headers = new Headers(options.headers);
    expect(headers.get("Authorization")).toBe("Bearer build-time-credential");
  });

  it("clearAuthCredential removes a stored credential", async () => {
    const { fetchApi, setAuthCredential, clearAuthCredential } = await import("./api");
    setAuthCredential("a-real-jwt-or-api-key");
    clearAuthCredential();

    await fetchApi("/prospects");

    const [, options] = fetchMock.mock.calls[0];
    const headers = new Headers(options.headers);
    expect(headers.has("Authorization")).toBe(false);
  });

  it("never sends the legacy X-Tenant-ID header", async () => {
    const { fetchApi, setAuthCredential } = await import("./api");
    setAuthCredential("a-real-jwt-or-api-key");

    await fetchApi("/prospects");

    const [, options] = fetchMock.mock.calls[0];
    const headers = new Headers(options.headers);
    expect(headers.has("X-Tenant-ID")).toBe(false);
  });

  it("throws with the backend's detail message on a non-ok response", async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: "Missing authentication credentials." }),
    });
    const { fetchApi } = await import("./api");

    await expect(fetchApi("/prospects")).rejects.toThrow("Missing authentication credentials.");
  });

  it("extracts readable messages from FastAPI's array-shaped 422 validation detail", async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({
        detail: [
          { loc: ["body", "email"], msg: "value is not a valid email address", type: "value_error" },
          { loc: ["body", "phone_number"], msg: "string does not match regex", type: "value_error" },
        ],
      }),
    });
    const { fetchApi } = await import("./api");

    await expect(fetchApi("/prospects")).rejects.toThrow(
      "value is not a valid email address, string does not match regex"
    );
  });

  it("falls back to a generic API error when detail is an array with no msg fields", async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({ detail: [{ loc: ["body"], type: "value_error" }] }),
    });
    const { fetchApi } = await import("./api");

    await expect(fetchApi("/prospects")).rejects.toThrow("API error: 422");
  });
});
