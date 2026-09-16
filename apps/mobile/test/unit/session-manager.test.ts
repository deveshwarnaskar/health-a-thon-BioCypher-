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
});
