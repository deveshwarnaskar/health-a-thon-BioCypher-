import type { ApiErrorDetails } from "../services/api/errors";
import type { AuthExpiredSignal } from "./authSignal";
import { createAuthExpiredSignal } from "./authSignal";
import type { AuthenticatedContext, AuthStatus } from "./types";

/**
 * Session boundary for the API layer.
 *
 * Gate 10B defines the contract only. The real Keycloak OIDC + PKCE
 * integration and expo-secure-store token persistence land in Gate 10C.
 * Until then every token/handling method FAILS LOUD instead of faking a
 * refresh or minting demo tokens.
 */
export interface AuthSessionProvider {
  getAccessToken(): Promise<string | null>;
  refreshSession(): Promise<string | null>;
  clearSession(): Promise<void>;
  getAuthenticatedContext(): Promise<AuthStatus>;
  /** 401 observed anywhere → observable signal for one clean session reset. */
  signalAuthExpired(error: ApiErrorDetails): void;
  onAuthExpired(listener: (error: ApiErrorDetails) => void): () => void;
}

export class AuthNotConfiguredError extends Error {
  constructor(method: string) {
    super(`${method} is not implemented until Gate 10C (OIDC auth shell). No fake tokens or refresh are produced.`);
    this.name = "AuthNotConfiguredError";
  }
}

/**
 * Stand-in provider active between Gate 10B and Gate 10C. Clearly announces
 * that authentication is not wired instead of presenting insecure
 * placeholders.
 */
export class NotConfiguredAuthSessionProvider implements AuthSessionProvider {
  private readonly signal: AuthExpiredSignal = createAuthExpiredSignal();

  async getAccessToken(): Promise<string | null> {
    return null;
  }

  async refreshSession(): Promise<string | null> {
    throw new AuthNotConfiguredError("refreshSession");
  }

  async clearSession(): Promise<void> {
    return Promise.resolve();
  }

  async getAuthenticatedContext(): Promise<AuthStatus> {
    return { state: "anonymous" };
  }

  signalAuthExpired(error: ApiErrorDetails): void {
    this.signal.emit(error);
  }

  onAuthExpired(listener: (error: ApiErrorDetails) => void): () => void {
    return this.signal.subscribe(listener);
  }
}

export type { AuthenticatedContext, AuthStatus };