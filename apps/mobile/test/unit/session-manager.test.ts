import { describe, it, expect, vi, beforeEach } from "vitest";
import { OidcSessionManager } from "../../src/auth/sessionManager";
import { InMemoryTokenStore } from "../../src/auth/tokenStore";
import { AuthTransientError, TokenNetworkError } from "../../src/auth/tokenEndpoint";
import { createAuthExpiredSignal } from "../../src/auth/authSignal";
import type { AuthFlowState } from "../../src/auth/authStateMachine";
import type { OidcConfig } from "../../src/auth/oidcConfig";
import type { OidcDiscovery } from "../../src/auth/discovery";
import type { OidcFlow } from "../../src/auth/oidcFlow";

const testConfig: OidcConfig = {
  issuerUrl: "http://keycloak.test/realms/test",
  realm: "test",
  clientId: "test-app",
  redirectUri: "test://callback",
  scopes: ["openid"],
};

const testDiscovery: OidcDiscovery = {
  issuer: "http://keycloak.test/realms/test",
  authorizationEndpoint: "http://keycloak.test/realms/test/protocol/openid-connect/auth",
  tokenEndpoint: "http://keycloak.test/realms/test/protocol/openid-connect/token",
  revocationEndpoint: "http://keycloak.test/realms/test/protocol/openid-connect/revoke",
  endSessionEndpoint: "http://keycloak.test/realms/test/protocol/openid-connect/logout",
};

function fakeOidcFlow(overrides: Partial<OidcFlow> = {}): OidcFlow {
  const defaults: OidcFlow = {
    authorize: async () => ({ status: "cancel" as const }),
    exchangeCode: async () => ({
      access_token: "at-test",
      refresh_token: "rt-test",
      id_token: "id-test",
      expires_in: 3600,
      token_type: "Bearer" as const,
    }),
    refresh: async () => ({
      access_token: "at-refreshed",
      refresh_token: "rt-refreshed",
      id_token: "id-refreshed",
      expires_in: 3600,
      token_type: "Bearer" as const,
    }),
    endSession: async () => {},
  };
  return { ...defaults, ...overrides };
}

function fakeApiClient(overrides: { requestResult?: unknown; requestError?: unknown } = {}) {
  return {
    request: overrides.requestError
      ? vi.fn(async () => { throw overrides.requestError; })
      : vi.fn(async () => overrides.requestResult ?? { actor_id: "a-1", tenant_id: "t-1", roles: ["patient"], facility_id: "f-1" }),
  } as any;
}

function collectStates(mgr: OidcSessionManager): AuthFlowState[] {
  const states: AuthFlowState[] = [];
  mgr.subscribe((s) => states.push(s));
  return states;
}

describe("OidcSessionManager", () => {
  let tokenStore: InMemoryTokenStore;
  let signal: ReturnType<typeof createAuthExpiredSignal>;

  beforeEach(() => {
    tokenStore = new InMemoryTokenStore();
    signal = createAuthExpiredSignal();
  });

  it("BOOTSTRAP_COMPLETE with no tokens → unauthenticated", async () => {
    const mgr = new OidcSessionManager({
      config: testConfig,
      discovery: testDiscovery,
      tokenStore,
      oidcFlow: fakeOidcFlow(),
      apiClient: fakeApiClient(),
      onAuthExpiredSignal: signal,
    });
    const states = collectStates(mgr);
    await mgr.init();
    expect(states.map((s) => s.name)).toEqual(["unauthenticated"]);
  });

  it("BOOTSTRAP_COMPLETE with refresh token → bootstrapping then refresh flow", async () => {
    await tokenStore.saveTokens({ accessToken: "at-old", refreshToken: "rt-old", idToken: "id-old" });
    const fakeApi = fakeApiClient({ requestResult: { actor_id: "a-1", tenant_id: "t-1", roles: ["patient"], facility_id: "f-1" } });
    const refreshSpy = vi.fn(async () => ({
      access_token: "at-new",
      refresh_token: "rt-new",
      id_token: "id-new",
      expires_in: 3600,
      token_type: "Bearer" as const,
    }));
    const flow = fakeOidcFlow({ refresh: refreshSpy });
    const mgr = new OidcSessionManager({
      config: testConfig,
      discovery: testDiscovery,
      tokenStore,
      oidcFlow: flow,
      apiClient: fakeApi,
      onAuthExpiredSignal: signal,
    });
    const states = collectStates(mgr);
    await mgr.init();
    expect(states[0]?.name).toBe("bootstrapping");
    expect(states.some((s) => s.name === "authenticated")).toBe(true);
    expect(refreshSpy).toHaveBeenCalledOnce();
    expect(fakeApi.request).toHaveBeenCalledOnce();
    const userState = states.find((s) => s.name === "authenticated");
    expect(userState).toBeDefined();
    expect(userState).toHaveProperty("user");
    expect(userState).toHaveProperty("accessToken");
  });

  it("signIn cancels → unauthenticated (no tokens saved)", async () => {
    const flow = fakeOidcFlow({
      authorize: async () => ({ status: "cancel" }),
    });
    const mgr = new OidcSessionManager({
      config: testConfig,
      discovery: testDiscovery,
      tokenStore,
      oidcFlow: flow,
      apiClient: fakeApiClient(),
      onAuthExpiredSignal: signal,
    });
    const states = collectStates(mgr);
    await mgr.init();
    await mgr.signIn();
    const lastState = states[states.length - 1];
    expect(lastState?.name).toBe("failed");
  });

  it("signIn success → exchangeCode → verifyWithBackend → authenticated", async () => {
    const authorizeSpy = vi.fn(async () => ({ status: "success" as const, code: "auth-code-123", codeVerifier: "verifier-123" }));
    const exchangeSpy = vi.fn(async () => ({
      access_token: "at-exchanged",
      refresh_token: "rt-exchanged",
      id_token: "id-exchanged",
      expires_in: 3600,
      token_type: "Bearer" as const,
    }));
    const flow = fakeOidcFlow({ authorize: authorizeSpy, exchangeCode: exchangeSpy });
    const mgr = new OidcSessionManager({
      config: testConfig,
      discovery: testDiscovery,
      tokenStore,
      oidcFlow: flow,
      apiClient: fakeApiClient(),
      onAuthExpiredSignal: signal,
    });
    const states = collectStates(mgr);
    await mgr.init();
    await mgr.signIn();
    expect(authorizeSpy).toHaveBeenCalledOnce();
    expect(exchangeSpy).toHaveBeenCalledOnce();
    const savedTokens = await tokenStore.getAccessToken();
    expect(savedTokens).toBe("at-exchanged");
    expect(states.some((s) => s.name === "authenticated")).toBe(true);
  });

  it("signOut clears tokens and dispatches LOGOUT", async () => {
    await tokenStore.saveTokens({ accessToken: "at", refreshToken: "rt", idToken: "id" });
    const flow = fakeOidcFlow({ endSession: vi.fn(async () => {}) });
    const mgr = new OidcSessionManager({
      config: testConfig,
      discovery: testDiscovery,
      tokenStore,
      oidcFlow: flow,
      apiClient: fakeApiClient(),
      onAuthExpiredSignal: signal,
    });
    const states = collectStates(mgr);
    await mgr.init();
    await mgr.signOut();
    expect(await tokenStore.getAccessToken()).toBeNull();
    expect(await tokenStore.getRefreshToken()).toBeNull();
    expect(states.some((s) => s.name === "unauthenticated")).toBe(true);
  });

  it("refreshOnce handles decisive failure (no refresh token) → RefreshInvalidatedError", async () => {
    const mgr = new OidcSessionManager({
      config: testConfig,
      discovery: testDiscovery,
      tokenStore,
      oidcFlow: fakeOidcFlow(),
      apiClient: fakeApiClient(),
      onAuthExpiredSignal: signal,
    });
    await mgr.init();
    const result = await mgr.refreshSession();
    expect(result).toBeNull();
  });

  it("transient refresh failure throws AuthTransientError", async () => {
    const flow = fakeOidcFlow({
      refresh: async () => { throw new TokenNetworkError(); },
    });
    const mgr = new OidcSessionManager({
      config: testConfig,
      discovery: testDiscovery,
      tokenStore,
      oidcFlow: flow,
      apiClient: fakeApiClient(),
      onAuthExpiredSignal: signal,
    });
    await tokenStore.saveTokens({ accessToken: "at", refreshToken: "rt", idToken: "id" });
    await mgr.init();
    await expect(mgr.refreshSession()).rejects.toThrow(AuthTransientError);
  });

  it("concurrent refreshSession calls latch onto exactly ONE issueRefresh call (single-flight mutex)", async () => {
    let refreshCalls = 0;
    const flow = fakeOidcFlow({
      refresh: vi.fn(async () => {
        refreshCalls += 1;
        await new Promise((resolve) => setTimeout(resolve, 20));
        return {
          access_token: "at-concurrent-refreshed",
          refresh_token: "rt-concurrent-refreshed",
          id_token: "id-concurrent-refreshed",
          expires_in: 3600,
          token_type: "Bearer" as const,
        };
      }),
    });
    const mgr = new OidcSessionManager({
      config: testConfig,
      discovery: testDiscovery,
      tokenStore,
      oidcFlow: flow,
      apiClient: fakeApiClient(),
      onAuthExpiredSignal: signal,
    });
    await tokenStore.saveTokens({ accessToken: "at-old", refreshToken: "rt-old", idToken: "id-old" });
    await mgr.init();
    refreshCalls = 0;

    const results = await Promise.all([
      mgr.refreshSession(),
      mgr.refreshSession(),
      mgr.refreshSession(),
      mgr.refreshSession(),
      mgr.refreshSession(),
    ]);

    expect(refreshCalls).toBe(1);
    expect(results).toEqual([
      "at-concurrent-refreshed",
      "at-concurrent-refreshed",
      "at-concurrent-refreshed",
      "at-concurrent-refreshed",
      "at-concurrent-refreshed",
    ]);
  });

  it("recoverPassword delegates to oidcFlow.recoverPassword", async () => {
    const recoverSpy = vi.fn(async () => {});
    const flow = fakeOidcFlow({ recoverPassword: recoverSpy });
    const mgr = new OidcSessionManager({
      config: testConfig,
      discovery: testDiscovery,
      tokenStore,
      oidcFlow: flow,
      apiClient: fakeApiClient(),
      onAuthExpiredSignal: signal,
    });
    await mgr.recoverPassword();
    expect(recoverSpy).toHaveBeenCalledWith(testConfig, testDiscovery);
  });

  it("calls onProtectedStateInvalidated callback on signOut", async () => {
    await tokenStore.saveTokens({ accessToken: "at", refreshToken: "rt", idToken: "id" });
    const onInvalidatedSpy = vi.fn();
    const mgr = new OidcSessionManager({
      config: testConfig,
      discovery: testDiscovery,
      tokenStore,
      oidcFlow: fakeOidcFlow(),
      apiClient: fakeApiClient(),
      onAuthExpiredSignal: signal,
      onProtectedStateInvalidated: onInvalidatedSpy,
    });
    await mgr.signOut();
    expect(onInvalidatedSpy).toHaveBeenCalledOnce();
  });

  it("verifyWithBackend uses /api/v2/auth/context and falls back to /verify if 404", async () => {
    const requestSpy = vi
      .fn()
      .mockRejectedValueOnce({ status: 404, code: "NOT_FOUND" })
      .mockResolvedValueOnce({
        actor_id: "a-fallback",
        tenant_id: "t-fallback",
        roles: ["patient"],
        facility_id: "f-fallback",
      });

    const flow = fakeOidcFlow({
      authorize: async () => ({ status: "success" as const, code: "c-1", codeVerifier: "v-1" }),
    });

    const mgr = new OidcSessionManager({
      config: testConfig,
      discovery: testDiscovery,
      tokenStore,
      oidcFlow: flow,
      apiClient: { request: requestSpy } as any,
      onAuthExpiredSignal: signal,
    });

    await mgr.signIn();
    expect(requestSpy).toHaveBeenCalledTimes(2);
    expect(requestSpy.mock.calls[0]?.[0]?.path).toBe("/api/v2/auth/context");
    expect(requestSpy.mock.calls[1]?.[0]?.path).toBe("/api/v2/auth/verify");
    const state = mgr.getState();
    expect(state.name).toBe("authenticated");
    if (state.name === "authenticated") {
      expect(state.user.actor_id).toBe("a-fallback");
    }
  });

  it("multi-user boundary: User A logs out, purges data, then User B logs in with clean boundary", async () => {
    let currentUserResponse = {
      actor_id: "user-a-1111",
      tenant_id: "tenant-a-1111",
      roles: ["patient"],
      facility_id: "fac-a",
      patient_id: "patient-a",
    };

    const requestSpy = vi.fn(async () => currentUserResponse);
    let codeVerifierIndex = 1;
    const flow = fakeOidcFlow({
      authorize: vi.fn(async () => ({
        status: "success" as const,
        code: `code-${codeVerifierIndex++}`,
        codeVerifier: "verifier-xyz",
      })),
      exchangeCode: vi.fn(async (_cfg, _disc, code) => ({
        access_token: `at-${code}`,
        refresh_token: `rt-${code}`,
        id_token: `id-${code}`,
        expires_in: 3600,
        token_type: "Bearer" as const,
      })),
    });

    const invalidatedSpy = vi.fn();
    const mgr = new OidcSessionManager({
      config: testConfig,
      discovery: testDiscovery,
      tokenStore,
      oidcFlow: flow,
      apiClient: { request: requestSpy } as any,
      onAuthExpiredSignal: signal,
      onProtectedStateInvalidated: invalidatedSpy,
    });

    // 1. User A logs in
    await mgr.signIn();
    let state = mgr.getState();
    expect(state.name).toBe("authenticated");
    if (state.name === "authenticated") {
      expect(state.user.actor_id).toBe("user-a-1111");
      expect(state.user.tenant_id).toBe("tenant-a-1111");
      expect(state.user.role).toBe("Patient");
    }
    expect(await tokenStore.getAccessToken()).toBe("at-code-1");

    // 2. User A logs out
    await mgr.signOut();
    expect(invalidatedSpy).toHaveBeenCalledTimes(1);
    expect(await tokenStore.getAccessToken()).toBeNull();
    expect(await tokenStore.getRefreshToken()).toBeNull();
    expect(mgr.getState().name).toBe("unauthenticated");

    // 3. User B logs in (different user, different tenant, different role)
    currentUserResponse = {
      actor_id: "user-b-2222",
      tenant_id: "tenant-b-2222",
      roles: ["doctor"],
      facility_id: "fac-b",
      patient_id: null as any,
    };

    await mgr.signIn();
    state = mgr.getState();
    expect(state.name).toBe("authenticated");
    if (state.name === "authenticated") {
      expect(state.user.actor_id).toBe("user-b-2222");
      expect(state.user.tenant_id).toBe("tenant-b-2222");
      expect(state.user.role).toBe("Doctor");
      expect(state.user.patient_id).toBeNull();
    }
    expect(await tokenStore.getAccessToken()).toBe("at-code-2");
  });

  it("signIn with email and password performs direct authentication", async () => {
    const fakeApi = {
      request: vi.fn(async ({ path, method }: any) => {
        if (path === "/api/v2/auth/login" && method === "POST") {
          return {
            access_token: "at-direct-123",
            refresh_token: "rt-direct-456",
            token_type: "bearer",
            expires_in: 900,
          };
        }
        if (path === "/api/v2/auth/context" || path === "/api/v2/auth/verify") {
          return {
            actor_id: "patient-direct-1",
            tenant_id: "thali-dev",
            roles: ["patient"],
            facility_id: "fac-1",
            patient_id: "pat-1",
          };
        }
        throw new Error(`Unexpected path: ${path}`);
      }),
    } as any;

    const mgr = new OidcSessionManager({
      config: testConfig,
      discovery: testDiscovery,
      tokenStore,
      oidcFlow: fakeOidcFlow(),
      apiClient: fakeApi,
      onAuthExpiredSignal: signal,
    });

    await mgr.init();
    await mgr.signIn("patient@thali.dev", "password123");

    const state = mgr.getState();
    expect(state.name).toBe("authenticated");
    if (state.name === "authenticated") {
      expect(state.user.actor_id).toBe("patient-direct-1");
      expect(state.user.tenant_id).toBe("thali-dev");
      expect(state.user.role).toBe("Patient");
      expect(state.accessToken).toBe("at-direct-123");
    }
    expect(await tokenStore.getAccessToken()).toBe("at-direct-123");
    expect(await tokenStore.getRefreshToken()).toBe("rt-direct-456");
  });

  it("signUp registers user and establishes authenticated session", async () => {
    const fakeApi = {
      request: vi.fn(async ({ path, body }: any) => {
        if (path === "/api/v2/auth/signup") {
          return {
            access_token: "at-signup-123",
            refresh_token: "rt-signup-456",
            token_type: "bearer",
            expires_in: 3600,
          };
        }
        if (path === "/api/v2/auth/context" || path === "/api/v2/auth/verify") {
          return {
            actor_id: "new-user-id",
            tenant_id: "thali-dev",
            roles: ["patient"],
            facility_id: "fac-1",
            patient_id: "pat-1",
          };
        }
        throw new Error(`Unexpected path: ${path}`);
      }),
    } as any;

    const mgr = new OidcSessionManager({
      config: testConfig,
      discovery: testDiscovery,
      tokenStore,
      oidcFlow: fakeOidcFlow(),
      apiClient: fakeApi,
      onAuthExpiredSignal: signal,
    });

    await mgr.init();
    await mgr.signUp({
      email: "newpatient@thali.dev",
      password: "password123",
      name: "New Patient",
      role: "patient",
    });

    const state = mgr.getState();
    expect(state.name).toBe("authenticated");
    if (state.name === "authenticated") {
      expect(state.user.actor_id).toBe("new-user-id");
      expect(state.accessToken).toBe("at-signup-123");
    }
  });

  it("forgotPassword and resetPassword invoke correct endpoints", async () => {
    const fakeApi = {
      request: vi.fn(async ({ path }: any) => {
        if (path === "/api/v2/auth/forgot-password") {
          return { status: "ok", message: "Instructions sent", reset_token: "tok-123" };
        }
        if (path === "/api/v2/auth/reset-password") {
          return { status: "ok", message: "Password updated" };
        }
        throw new Error(`Unexpected path: ${path}`);
      }),
    } as any;

    const mgr = new OidcSessionManager({
      config: testConfig,
      discovery: testDiscovery,
      tokenStore,
      oidcFlow: fakeOidcFlow(),
      apiClient: fakeApi,
      onAuthExpiredSignal: signal,
    });

    const forgotRes = await mgr.forgotPassword("user@thali.dev");
    expect(forgotRes.status).toBe("ok");
    expect(forgotRes.reset_token).toBe("tok-123");

    const resetRes = await mgr.resetPassword("tok-123", "newPassword123");
    expect(resetRes.status).toBe("ok");
  });
});

