import type { AuthSessionProvider } from "./AuthSessionProvider";
import type { ApiErrorDetails } from "../services/api/errors";
import { isAuthExpiredSignal } from "../services/api/errors";
import { createAuthExpiredSignal } from "./authSignal";
import type { AuthExpiredSignal } from "./authSignal";
import type { TokenStore } from "./tokenStore";
import type { OidcFlow } from "./oidcFlow";
import type { OidcConfig } from "./oidcConfig";
import type { OidcDiscovery } from "./discovery";
import type { ApiClient } from "../services/api/client";
import {
  authStateReducer,
  INITIAL_STATE,
  type AuthFlowState,
  type AuthFlowEvent,
  type AuthUser,
  type AuthErrorCategory,
} from "./authStateMachine";
import {
  AuthTransientError,
  TokenEndpointError,
  classifyRefreshOutcome,
} from "./tokenEndpoint";
import { buildAuthUser } from "./authenticatedUser";
import { authLog } from "./authLog";
import { toAuthenticatedContext } from "./types";

export type SessionManagerDependencies = {
  config: OidcConfig;
  discovery: OidcDiscovery;
  tokenStore: TokenStore;
  oidcFlow: OidcFlow;
  apiClient: ApiClient;
  onAuthExpiredSignal?: AuthExpiredSignal;
  onProtectedStateInvalidated?: () => void;
};

export type StateListener = (state: AuthFlowState) => void;

export class OidcSessionManager implements AuthSessionProvider {
  private readonly config: OidcConfig;
  private readonly discovery: OidcDiscovery;
  private readonly tokenStore: TokenStore;
  private readonly oidcFlow: OidcFlow;
  private readonly apiClient: ApiClient;
  private readonly signal: AuthExpiredSignal;
  private readonly onProtectedStateInvalidated?: () => void;

  private state: AuthFlowState = INITIAL_STATE;
  private stateListeners = new Set<StateListener>();
  private inFlightRefresh: Promise<{ accessToken: string }> | null = null;
  private disposed = false;

  constructor(deps: SessionManagerDependencies) {
    this.config = deps.config;
    this.discovery = deps.discovery;
    this.tokenStore = deps.tokenStore;
    this.oidcFlow = deps.oidcFlow;
    this.apiClient = deps.apiClient;
    this.signal = deps.onAuthExpiredSignal ?? createAuthExpiredSignal();
    this.onProtectedStateInvalidated = deps.onProtectedStateInvalidated;
  }

  // ─── AuthSessionProvider interface ───────────────────────────────────────

  async getAccessToken(): Promise<string | null> {
    return this.tokenStore.getAccessToken();
  }

  async refreshSession(): Promise<string | null> {
    // Decisive failure (invalid_grant) → null AND local session cleared.
    // Transient failure (network / 5xx) → AuthTransientError propagates so the
    // caller does NOT treat the session as expired.
    try {
      const refreshed = await this.refreshOnce();
      if (refreshed && (this.state.name === "authenticated" || this.state.name === "session_expiring")) {
        this.dispatch({ type: "REFRESH_SUCCESS", accessToken: refreshed.accessToken });
        return refreshed.accessToken;
      }
      await this.tokenStore.clear();
      if (this.state.name === "authenticated" || this.state.name === "session_expiring") {
        this.dispatch({ type: "REFRESH_FAILURE", error: refreshed });
      }
      return null;
    } catch (cause) {
      if (cause instanceof AuthTransientError) throw cause;
      await this.tokenStore.clear();
      if (this.state.name === "authenticated" || this.state.name === "session_expiring") {
        this.dispatch({ type: "REFRESH_FAILURE", error: cause });
      }
      return null;
    }
  }

  async clearSession(): Promise<void> {
    await this.tokenStore.clear();
  }

  async getAuthenticatedContext() {
    const user = this.getUserFromState();
    if (!user) return { state: "anonymous" as const };
    return {
      state: "authenticated" as const,
      context: toAuthenticatedContext({
        actor_id: user.actor_id,
        tenant_id: user.tenant_id,
        roles: user.roles,
        facility_id: user.facility_id,
      }),
    };
  }

  signalAuthExpired(error: ApiErrorDetails): void {
    if (
      this.state.name === "session_expired" ||
      this.state.name === "deactivated" ||
      this.state.name === "access_denied"
    ) {
      return;
    }

    this.clearSessionSync();
    this.dispatch({ type: "SESSION_EXPIRED", error });
    this.signal.emit(error);
    this.onProtectedStateInvalidated?.();
    authLog({ event: "session_expired", category: error.code ?? "UNAUTHORIZED" });
  }

  onAuthExpired(listener: (error: ApiErrorDetails) => void): () => void {
    return this.signal.subscribe(listener);
  }

  // ─── extended API ────────────────────────────────────────────────────────

  getState(): AuthFlowState {
    return this.state;
  }

  subscribe(listener: StateListener): () => void {
    this.stateListeners.add(listener);
    return () => {
      this.stateListeners.delete(listener);
    };
  }

  async init(): Promise<void> {
    if (this.disposed) return;

    const hasTokens = (await this.tokenStore.getRefreshToken()) !== null;
    this.dispatch({ type: "BOOTSTRAP_COMPLETE", hasTokens });

    if (!hasTokens) return;

    await this.restoreSession();
  }

  async signIn(): Promise<void> {
    if (this.state.name === "authenticating") return;

    this.dispatch({ type: "AUTH_INITIATED" });
    authLog({ event: "auth_initiated" });

    try {
      const result = await this.oidcFlow.authorize(this.config, this.discovery);

      if (result.status !== "success") {
        this.dispatch({
          type: "AUTH_ERROR",
          category: result.status === "error" ? "oidc_denied" : "oidc_canceled",
          error: result.status === "error" ? result.message : undefined,
        });
        return;
      }

      await this.completeAuthFromCode(result.code, result.codeVerifier);
    } catch (cause) {
      if (cause instanceof AuthTransientError) {
        this.dispatch({ type: "AUTH_ERROR", category: cause.category, error: cause });
        return;
      }
      authLog({ event: "auth_error", status: String(cause) });
      this.dispatch({
        type: "AUTH_ERROR",
        category: this.categorizeError(cause),
        error: cause,
      });
    }
  }

  async signOut(): Promise<void> {
    authLog({ event: "sign_out" });

    const idToken = await this.tokenStore.getIdToken();
    await this.tokenStore.clear();
    this.onProtectedStateInvalidated?.();

    if (idToken) {
      await this.oidcFlow
        .endSession(this.discovery, idToken, this.config.redirectUri)
        .catch(() => {});
    }

    this.dispatch({ type: "LOGOUT" });
  }

  // ─── internals ───────────────────────────────────────────────────────────

  private dispatch(event: AuthFlowEvent): void {
    try {
      this.state = authStateReducer(this.state, event);
    } catch (err) {
      authLog({ event: "state_machine_error", status: String(err) });
      return;
    }

    for (const listener of [...this.stateListeners]) {
      listener(this.state);
    }
  }

  private getUserFromState(): AuthUser | null {
    if ("user" in this.state) return this.state.user as AuthUser;
    return null;
  }

  private clearSessionSync(): void {
    this.tokenStore.clear().catch(() => {});
  }

  private async completeAuthFromCode(code: string, codeVerifier: string): Promise<void> {
    let tokenResponse;
    try {
      tokenResponse = await this.oidcFlow.exchangeCode(
        this.config,
        this.discovery,
        code,
        codeVerifier
      );
    } catch (cause) {
      if (cause instanceof AuthTransientError) throw cause;
      throw new AuthTransientError("network", cause);
    }

    await this.tokenStore.saveTokens({
      accessToken: tokenResponse.access_token,
      refreshToken: tokenResponse.refresh_token,
      idToken: tokenResponse.id_token,
    });

    const user = await this.verifyWithBackend();
    if (user === null) return;

    if (!user.role) {
      this.dispatch({ type: "ACCESS_DENIED", reason: "unknown_role", user });
      return;
    }

    authLog({ event: "auth_success", status: "ok" });
    this.dispatch({
      type: "AUTH_SUCCESS",
      user,
      accessToken: tokenResponse.access_token,
    });
  }

  private async restoreSession(): Promise<void> {
    try {
      const refreshed = await this.refreshOnce();
      const user = await this.verifyWithBackend();

      if (refreshed === null || user === null) return;

      if (!user.role) {
        this.dispatch({ type: "ACCESS_DENIED", reason: "unknown_role", user });
        return;
      }

      this.dispatch({ type: "AUTH_SUCCESS", user, accessToken: refreshed.accessToken });
      authLog({ event: "session_restored", status: "ok" });
    } catch (cause) {
      if (cause instanceof AuthTransientError) {
        this.dispatch({ type: "AUTH_ERROR", category: cause.category, error: cause });
        return;
      }

      if (cause instanceof RefreshInvalidatedError) {
        this.dispatch({ type: "REFRESH_FAILURE", error: cause });
        return;
      }

      authLog({ event: "restore_failed", status: String(cause) });
      this.dispatch({
        type: "AUTH_ERROR",
        category: this.categorizeError(cause),
        error: cause,
      });
    }
  }

  /**
   * Single-flight refresh. Resolves to the new access token, `null` on a
   * DECISIVE refresh failure (invalid_grant / no refresh token — local tokens
   * cleared and the session expired), or rejects with AuthTransientError on a
   * transient network/server failure (session preserved).
   */
  private async refreshOnce(): Promise<{ accessToken: string } | null> {
    if (this.inFlightRefresh) return this.inFlightRefresh;

    this.inFlightRefresh = this.issueRefresh();
    try {
      return await this.inFlightRefresh;
    } finally {
      this.inFlightRefresh = null;
    }
  }

  private async issueRefresh(): Promise<{ accessToken: string }> {
    const refreshToken = await this.tokenStore.getRefreshToken();
    if (!refreshToken) {
      throw new TokenEndpointError("No refresh token available.", 0, "no_refresh_token");
    }

    try {
      const response = await this.oidcFlow.refresh(
        this.discovery,
        refreshToken,
        this.config.clientId,
        this.config.scopes
      );

      await this.tokenStore.saveTokens({
        accessToken: response.access_token,
        refreshToken: response.refresh_token,
        idToken: response.id_token,
      });

      authLog({ event: "refresh_success", status: "ok" });
      return { accessToken: response.access_token };
    } catch (cause) {
      const outcome = classifyRefreshOutcome(cause);
      authLog({
        event: "refresh_failure",
        status: outcome === "transient" ? "transient" : "invalid_session",
      });

      if (outcome === "transient") {
        throw new AuthTransientError(
          cause instanceof TokenEndpointError && cause.httpStatus >= 500
            ? "server_unavailable"
            : "network",
          cause
        );
      }

      // Decisive: refresh token is no longer usable.
      await this.tokenStore.clear();
      throw new RefreshInvalidatedError(cause);
    }
  }

  private async verifyWithBackend(): Promise<AuthUser | null> {
    try {
      const verifyResponse = await this.apiClient.request<{
        actor_id: string;
        tenant_id: string;
        roles: string[];
        facility_id: string | null;
      }>({
        method: "GET",
        path: "/api/v2/auth/verify",
      });

      return buildAuthUser(toAuthenticatedContext(verifyResponse));
    } catch (cause) {
      const details = cause as ApiErrorDetails;
      if (isAuthExpiredSignal(details)) {
        this.dispatch({ type: "SESSION_EXPIRED", error: cause });
        return null;
      }

      if (details.kind === "FORBIDDEN") {
        this.dispatch({ type: "DEACTIVATED" });
        return null;
      }

      if (cause instanceof AuthTransientError) throw cause;
      throw new AuthTransientError("network", cause);
    }
  }

  private categorizeError(error: unknown): AuthErrorCategory {
    if (error instanceof AuthTransientError) return error.category;

    const msg = error instanceof Error ? error.message : String(error);
    if (/(network|refused|unreachable|connect)/i.test(msg)) return "network";
    if (/timeout/i.test(msg)) return "timeout";
    if (/50[0-9]/.test(msg)) return "server_unavailable";
    return "unknown";
  }
}

/** Internal marker: the refresh token is definitively invalid (session ended). */
export class RefreshInvalidatedError extends Error {
  constructor(cause?: unknown) {
    super("The refresh token is invalid or has expired.");
    this.name = "RefreshInvalidatedError";
    if (cause) (this as { cause?: unknown }).cause = cause;
  }
}