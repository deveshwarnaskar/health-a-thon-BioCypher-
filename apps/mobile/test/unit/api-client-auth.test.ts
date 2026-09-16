import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiClient } from "../../src/services/api/client";
import { readApiConfig, resetApiConfig } from "../../src/services/api/config";
import { isAuthExpiredSignal } from "../../src/services/api/errors";
import { AuthTransientError } from "../../src/auth/tokenEndpoint";
import type { AuthSessionProvider } from "../../src/auth/AuthSessionProvider";

function jsonResponse(status: number, body: unknown, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), { status, headers });
}

function fakeAuth(overrides: Partial<AuthSessionProvider> = {}): AuthSessionProvider {
  return {
    getAccessToken: async () => "tok-initial",
    refreshSession: async () => "tok-refreshed",
    clearSession: async () => {},
    getAuthenticatedContext: async () => ({ state: "anonymous" as const }),
    signalAuthExpired: vi.fn(),
    onAuthExpired: () => () => {},
    ...overrides,
  };
}

function makeClient(
  fetchImpl: typeof fetch,
  authProvider?: AuthSessionProvider,
  correlationId?: string
) {
  return new ApiClient({
    config: readApiConfig({ EXPO_PUBLIC_API_BASE_URL: "http://api.test", ...process.env }),
    fetchImpl: fetchImpl as typeof fetch,
    createCorrelationId: correlationId ? () => correlationId : undefined,
    authProvider,
  });
}

describe("ApiClient auth integration", () => {
  beforeEach(() => {
    resetApiConfig();
  });

  it("no authProvider: fires onAuthExpired immediately on 401 (legacy path)", async () => {
    const onAuthExpired = vi.fn();
    const fetchImpl = vi.fn(async () => jsonResponse(401, {}));
    const client = makeClient(fetchImpl, undefined, "corr-legacy");
    await expect(
      client.request({ method: "GET", path: "/x", onAuthExpired })
    ).rejects.toThrow();
    expect(onAuthExpired).toHaveBeenCalledOnce();
  });

  it("with authProvider: 401 triggers refreshSession + retry with same correlation and idempotency key", async () => {
    let callCount = 0;
    const fetchImpl = vi.fn(async () => {
      callCount += 1;
      if (callCount === 1) return jsonResponse(401, {});
      return jsonResponse(200, { ok: true });
    });
    const refreshSession = vi.fn(async () => "tok-refreshed");
    const auth = fakeAuth({ refreshSession });
    const client = makeClient(fetchImpl, auth, "corr-1");

    const result = await client.request<{ ok: boolean }>({
      method: "POST",
      path: "/api/v2/test",
      body: { data: 1 },
      idempotencyKey: "idem-abc",
    });
    expect(result.ok).toBe(true);
    expect(refreshSession).toHaveBeenCalledOnce();
    expect(fetchImpl).toHaveBeenCalledTimes(2);

    const calls = fetchImpl.mock.calls as unknown as [string, RequestInit][];
    const firstCall = calls[0]!;
    const secondCall = calls[1]!;
    const getHeader = (call: [string, RequestInit], key: string) => {
      const h = call[1].headers as Record<string, string>;
      return h[key] ?? (call[1].headers as Headers).get(key);
    };
    expect(getHeader(firstCall, "X-Correlation-ID")).toBe("corr-1");
    expect(getHeader(secondCall, "X-Correlation-ID")).toBe("corr-1");
    expect(getHeader(firstCall, "Idempotency-Key")).toBe("idem-abc");
    expect(getHeader(secondCall, "Idempotency-Key")).toBe("idem-abc");
  });

  it("transient refresh failure maps to NETWORK_ERROR without signalling auth-expired", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(401, {}));
    const auth = fakeAuth({
      refreshSession: async () => { throw new AuthTransientError("network"); },
    });
    const client = makeClient(fetchImpl, auth, "corr-transient");
    const thrown = await client
      .request({ method: "GET", path: "/x" })
      .then(() => null, (err) => err);
    expect(thrown.kind).toBe("NETWORK_ERROR");
    expect(auth.signalAuthExpired).not.toHaveBeenCalled();
  });

  it("decisive refresh failure signals auth-expired", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(401, {}));
    const auth = fakeAuth({
      refreshSession: async () => null,
    });
    const client = makeClient(fetchImpl, auth, "corr-decisive");
    const thrown = await client
      .request({ method: "GET", path: "/x" })
      .then(() => null, (err) => err);
    expect(isAuthExpiredSignal(thrown)).toBe(true);
    expect(auth.signalAuthExpired).toHaveBeenCalledOnce();
  });
});
