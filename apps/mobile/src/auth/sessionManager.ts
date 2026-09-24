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
import { decodeJwtPayload } from "./jwt";
import { localSessionIsolation } from "../db/isolation";
import * as SecureStore from "expo-secure-store";

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

  async signIn(email?: string, password?: string): Promise<void> {
    if (this.state.name === "authenticating") return;

    this.dispatch({ type: "AUTH_INITIATED" });
    authLog({ event: "auth_initiated" });

    if (email !== undefined && password !== undefined) {
      try {
        const response = await this.apiClient.request<{
          access_token: string;
          refresh_token: string;
          token_type?: string;
          expires_in?: number;
        }>({
          method: "POST",
          path: "/api/v2/auth/login",
          body: { email, password },
        });

        await this.tokenStore.saveTokens({
          accessToken: response.access_token,
          refreshToken: response.refresh_token,
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
          accessToken: response.access_token,
        });
        return;
      } catch (cause: any) {
        const category =
          cause instanceof AuthTransientError
            ? cause.category
            : this.categorizeError(cause);
        authLog({ event: "auth_error", category, status: String(cause) });
        this.dispatch({
          type: "AUTH_ERROR",
          category,
          error: cause?.message || cause,
        });
        return;
      }
    }

    try {
      const result = await this.oidcFlow.authorize(this.config, this.discovery);

      if (result.status !== "success") {
        authLog({
          event: "oidc_result_not_success",
          status: result.status,
          category: result.status === "error" ? "oidc_denied" : "oidc_canceled",
        });
        this.dispatch({
          type: "AUTH_ERROR",
          category: result.status === "error" ? "oidc_denied" : "oidc_canceled",
          error: result.status === "error" ? result.message : undefined,
        });
        return;
      }

      await this.completeAuthFromCode(result.code, result.codeVerifier);
    } catch (cause) {
      const category =
        cause instanceof AuthTransientError
          ? cause.category
          : this.categorizeError(cause);
      authLog({ event: "auth_error", category, status: String(cause) });
      this.dispatch({
        type: "AUTH_ERROR",
        category,
        error: cause,
      });
    }
  }

  async signOut(): Promise<void> {
    authLog({ event: "sign_out" });

    const refreshToken = await this.tokenStore.getRefreshToken();
    const idToken = await this.tokenStore.getIdToken();
    await this.tokenStore.clear();
    this.onProtectedStateInvalidated?.();

    if (refreshToken && !this.discovery.tokenEndpoint.includes("openid-connect")) {
      try {
        await this.apiClient.request({
          method: "POST",
          path: "/api/v2/auth/logout",
          body: { refresh_token: refreshToken },
        });
      } catch {}
    } else if (idToken) {
      await this.oidcFlow
        .endSession(this.discovery, idToken, this.config.redirectUri)
        .catch(() => {});
    }

    this.dispatch({ type: "LOGOUT" });
  }

  async deleteAccount(phone: string): Promise<void> {
    authLog({ event: "delete_account" });
    const cleanPhone = phone.trim();

    try {
      await this.apiClient.request({
        method: "DELETE",
        path: "/api/v2/auth/account",
        body: { phone: cleanPhone },
      });
    } catch (err: any) {
      // Fallback: try POST /api/v2/auth/delete-account in case HTTP client strips body in DELETE
      try {
        await this.apiClient.request({
          method: "POST",
          path: "/api/v2/auth/delete-account",
          body: { phone: cleanPhone },
        });
      } catch {
        throw err;
      }
    }

    const user = this.getUserFromState();
    if (user?.actor_id) {
      try {
        await SecureStore.deleteItemAsync(`thali.patient.signup_name_${user.actor_id}`).catch(() => {});
        await SecureStore.deleteItemAsync(`thali.patient.signup_phone_${user.actor_id}`).catch(() => {});
      } catch {}
    }
    try {
      await SecureStore.deleteItemAsync("thali.patient.signup_name").catch(() => {});
      await SecureStore.deleteItemAsync("thali.patient.signup_phone").catch(() => {});
    } catch {}

    await this.tokenStore.clear();
    this.onProtectedStateInvalidated?.();
    this.dispatch({ type: "LOGOUT" });
  }

  canRecoverPassword(): boolean {
    return typeof (this.oidcFlow as any)?.recoverPassword === "function";
  }

  async recoverPassword(): Promise<void> {
    if (this.oidcFlow.recoverPassword) {
      await this.oidcFlow.recoverPassword(this.config, this.discovery);
    }
  }

  async signUp(data: {
    email: string;
    password: string;
    name?: string;
    phone?: string;
    role?: string;
    invite_code?: string;
  }): Promise<{ user_status?: string; role?: string }> {
    if (this.state.name === "authenticating") return {};

    this.dispatch({ type: "AUTH_INITIATED" });
    authLog({ event: "auth_initiated" });

    try {
      const response = await this.apiClient.request<{
        access_token: string;
        refresh_token: string;
        token_type?: string;
        expires_in?: number;
        user_status?: string;
        role?: string;
      }>({
        method: "POST",
        path: "/api/v2/auth/signup",
        body: data,
      });

      await this.tokenStore.saveTokens({
        accessToken: response.access_token,
        refreshToken: response.refresh_token,
      });

      if (data.name) {
        try {
          await SecureStore.setItemAsync("thali.user.signup_name", data.name);
          await SecureStore.setItemAsync("thali.doctor.signup_name", data.name);
          await SecureStore.setItemAsync("thali.patient.signup_name", data.name);
        } catch {}
      }

      if (data.phone) {
        try {
          await SecureStore.setItemAsync("thali.patient.signup_phone", data.phone);
        } catch {}
      }

      const user = await this.verifyWithBackend();
      if (user === null) return { user_status: response.user_status, role: response.role };

      if (data.name) {
        user.name = data.name;
        try {
          await SecureStore.setItemAsync(`thali.user.signup_name_${user.actor_id}`, data.name);
          await SecureStore.setItemAsync(`thali.doctor.signup_name_${user.actor_id}`, data.name);
          await SecureStore.setItemAsync(`thali.patient.signup_name_${user.actor_id}`, data.name);
        } catch {}
      }

      if (data.phone) {
        user.phone = data.phone;
        try {
          await SecureStore.setItemAsync(`thali.patient.signup_phone_${user.actor_id}`, data.phone);
        } catch {}
      }

      if (!user.role) {
        this.dispatch({ type: "ACCESS_DENIED", reason: "unknown_role", user });
        return { user_status: response.user_status, role: response.role };
      }

      authLog({ event: "auth_success", status: "ok" });
      this.dispatch({
        type: "AUTH_SUCCESS",
        user,
        accessToken: response.access_token,
      });
      return { user_status: response.user_status, role: response.role };
    } catch (cause: any) {
      const category =
        cause instanceof AuthTransientError
          ? cause.category
          : this.categorizeError(cause);
      authLog({ event: "auth_error", category, status: String(cause) });
      this.dispatch({
        type: "AUTH_ERROR",
        category,
        error: cause?.message || cause,
      });
      throw cause;
    }
  }

  async forgotPassword(email: string): Promise<{ status: string; message: string; reset_token?: string | null }> {
    return await this.apiClient.request<{
      status: string;
      message: string;
      reset_token?: string | null;
    }>({
      method: "POST",
      path: "/api/v2/auth/forgot-password",
      body: { email },
    });
  }

  async resetPassword(token: string, newPassword: string): Promise<{ status: string; message: string }> {
    return await this.apiClient.request<{
      status: string;
      message: string;
    }>({
      method: "POST",
      path: "/api/v2/auth/reset-password",
      body: { token, new_password: newPassword },
    });
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
    authLog({ event: "complete_auth_start" });
    let tokenResponse;
    try {
      tokenResponse = await this.oidcFlow.exchangeCode(
        this.config,
        this.discovery,
        code,
        codeVerifier
      );
      authLog({ event: "exchange_code_success", status: "ok" });
    } catch (cause) {
      authLog({ event: "exchange_code_error", status: String(cause) });
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
      let accessToken: string;
      let newRefreshToken: string | undefined;

      if (!this.discovery.tokenEndpoint.includes("openid-connect")) {
        const refreshRes = await this.apiClient.request<{
          access_token: string;
          refresh_token: string;
        }>({
          method: "POST",
          path: "/api/v2/auth/refresh",
          body: { refresh_token: refreshToken },
        });
        accessToken = refreshRes.access_token;
        newRefreshToken = refreshRes.refresh_token;
      } else {
        const response = await this.oidcFlow.refresh(
          this.discovery,
          refreshToken,
          this.config.clientId,
          this.config.scopes
        );
        accessToken = response.access_token;
        newRefreshToken = response.refresh_token;
      }

      await this.tokenStore.saveTokens({
        accessToken,
        refreshToken: newRefreshToken,
      });

      authLog({ event: "refresh_success", status: "ok" });
      return { accessToken };
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
      let verifyResponse: {
        actor_id: string;
        tenant_id: string;
        roles: string[];
        facility_id: string | null;
        patient_id?: string | null;
      };

      try {
        const contextResponse = await this.apiClient.request<{
          actor_id: string;
          tenant_id: string;
          roles: string[];
          facility_id: string | null;
          patient_id?: string | null;
          onboarding_state?: string;
        }>({
          method: "GET",
          path: "/api/v2/auth/context",
        });
        verifyResponse = contextResponse;
      } catch (contextErr: any) {
        if (
          contextErr?.status === 404 ||
          contextErr?.code === "NOT_FOUND" ||
          contextErr?.kind === "NOT_FOUND"
        ) {
          verifyResponse = await this.apiClient.request<{
            actor_id: string;
            tenant_id: string;
            roles: string[];
            facility_id: string | null;
          }>({
            method: "GET",
            path: "/api/v2/auth/verify",
          });
        } else {
          throw contextErr;
        }
      }

      const token = await this.tokenStore.getAccessToken();
      const idToken = await this.tokenStore.getIdToken();
      const claims = token ? decodeJwtPayload(token) : null;
      const idClaims = idToken ? decodeJwtPayload(idToken) : null;
      const patientId =
        verifyResponse.patient_id ??
        (typeof claims?.patient_id === "string" ? claims.patient_id : null) ??
        (typeof idClaims?.patient_id === "string" ? idClaims.patient_id : null);

      let userName: string | null = (verifyResponse as any).name ?? null;
      if (!userName) {
        try {
          userName = await SecureStore.getItemAsync(`thali.user.signup_name_${verifyResponse.actor_id}`);
          if (!userName) {
            userName = await SecureStore.getItemAsync(`thali.doctor.signup_name_${verifyResponse.actor_id}`);
          }
          if (!userName) {
            userName = await SecureStore.getItemAsync(`thali.patient.signup_name_${verifyResponse.actor_id}`);
          }
          if (!userName) {
            userName = await SecureStore.getItemAsync("thali.doctor.signup_name");
          }
          if (!userName) {
            userName = await SecureStore.getItemAsync("thali.patient.signup_name");
          }
          if (!userName) {
            userName = await SecureStore.getItemAsync("thali.user.signup_name");
          }
        } catch {}
      }

      if (userName) {
        try {
          await SecureStore.setItemAsync(`thali.user.signup_name_${verifyResponse.actor_id}`, userName);
        } catch {}
      }

      let userPhone: string | null = (verifyResponse as any).phone ?? null;
      if (!userPhone) {
        try {
          userPhone = await SecureStore.getItemAsync(`thali.patient.signup_phone_${verifyResponse.actor_id}`);
          if (!userPhone) {
            userPhone = await SecureStore.getItemAsync("thali.patient.signup_phone");
          }
        } catch {}
      }

      const user = buildAuthUser(
        toAuthenticatedContext(verifyResponse, patientId),
        userName,
        userPhone,
        (verifyResponse as any).email ?? null
      );

      // Local session isolation (Gate 10O): initialize active session context
      localSessionIsolation.setContext({
        tenantId: user.tenant_id,
        userId: user.actor_id,
        roles: user.roles,
        facilityId: user.facility_id,
        patientId: user.patient_id,
      });

      return user;
    } catch (cause) {
      authLog({ event: "verify_backend_error", status: String(cause) });
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