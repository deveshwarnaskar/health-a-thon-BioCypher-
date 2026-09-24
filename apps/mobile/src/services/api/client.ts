import type { ZodType } from "zod";
import { getApiConfig, requireConfigured, type AppApiConfig } from "./config";
import { assembleHeaders } from "./headers";
import { newCorrelationId } from "./correlation";
import {
  isAuthExpiredSignal,
  mapHttpError,
  mapNetworkError,
  type ApiErrorDetails,
} from "./errors";
import type { AuthSessionProvider } from "../../auth/AuthSessionProvider";
import { AuthTransientError } from "../../auth/tokenEndpoint";

export type ApiMethod = "GET" | "POST" | "PATCH" | "DELETE";

export type ApiRequestOptions<TResponse> = {
  method: ApiMethod;
  path: string;
  body?: unknown;
  token?: string;
  idempotencyKey?: string;
  schema?: ZodType<TResponse>;
  onAuthExpired?: (error: ApiErrorDetails) => void;
  signal?: AbortSignal;
};

function isAuthTokenEndpoint(path: string): boolean {
  return path.startsWith("/api/v2/auth");
}

export type ApiDependencies = {
  config?: AppApiConfig;
  fetchImpl?: typeof fetch;
  createCorrelationId?: () => string;
  /**
   * Real session boundary (Gate 10C). When present, a 401 triggers exactly ONE
   * token refresh and a single retry with the refreshed token, reusing the
   * SAME correlation ID and the SAME Idempotency-Key so no mutation is
   * duplicated. Transient refresh failures (network/5xx) surface as a
   * retryable connection error WITHOUT logging the user out. When absent,
   * Gate 10B behaviour is preserved: the auth-expired signal fires immediately.
   */
  authProvider?: AuthSessionProvider;
};

type RawResult = {
  ok: boolean;
  raw: Response;
  body: unknown;
  error?: ApiErrorDetails;
};

/**
 * Single HTTP boundary for the mobile app. Centralizes:
 * - X-Correlation-ID on every request
 * - Authorization: Bearer <token> when a token is supplied
 * - Idempotency-Key on mutations
 * - typed error normalization (never leaks stack traces)
 * - auth-expired handling: one refresh + one retry (token refresh), then a
 *   session-expired signal (never an infinite retry loop)
 *
 * Endpoint URLs are never hard-coded in callers; they come from
 * `src/services/api/endpoints/*`.
 */
export class ApiClient {
  private readonly config: AppApiConfig;
  private readonly fetchImpl: typeof fetch;
  private readonly createCorrelationId: () => string;
  private authProvider?: AuthSessionProvider;

  constructor(deps: ApiDependencies = {}) {
    this.config = deps.config ?? getApiConfig();
    this.fetchImpl = deps.fetchImpl ?? fetch;
    this.createCorrelationId = deps.createCorrelationId ?? newCorrelationId;
    this.authProvider = deps.authProvider;
  }

  /**
   * Wires the real session boundary after construction. The session manager
   * depends on the client (it calls /auth/verify), so the reference is
   * established in one place here instead of at module load.
   */
  setAuthProvider(provider: AuthSessionProvider): void {
    this.authProvider = provider;
  }

  async request<TResponse>(options: ApiRequestOptions<TResponse>): Promise<TResponse> {
    requireConfigured(this.config);

    const correlationId = this.createCorrelationId();
    const hasBody = options.body !== undefined;

    let token: string | undefined = options.token;
    if (!token && this.authProvider) {
      token = (await this.authProvider.getAccessToken()) ?? undefined;
    }

    let result = await this.fetchAttempt(
      options,
      correlationId,
      token,
      hasBody
    );

    // Exactly one refresh + one retry on auth-expired. Any subsequent 401 is
    // surfaced as a session-expired signal, never retried again.
    if (
      !result.ok &&
      result.error &&
      isAuthExpiredSignal(result.error) &&
      this.authProvider &&
      !isAuthTokenEndpoint(options.path)
    ) {
      try {
        const refreshed = await this.authProvider.refreshSession();
        if (refreshed) {
          result = await this.fetchAttempt(
            options,
            correlationId,
            refreshed,
            hasBody
          );
        }
      } catch (cause) {
        // A transient refresh failure (network / 5xx) is NOT an authentication
        // failure: the session is preserved and the user sees a safe retryable
        // connection error instead of being logged out.
        if (cause instanceof AuthTransientError) {
          throw mapTransientError(cause);
        }
        // Any other refresh failure (provider exception) decays into the
        // generic safe error; the session must not silently loop.
      }

      if (!result.ok && result.error && isAuthExpiredSignal(result.error)) {
        this.signalsAuthExpired(result.error);
        this.notifyAuthExpired(options, result.error);
        throw result.error;
      }
    }

    if (!result.ok) {
      const error = result.error!;
      if (isAuthExpiredSignal(error) && !this.authProvider) {
        this.notifyAuthExpired(options, error);
      }
      throw error;
    }

    if (options.schema) {
      const parsed = options.schema.safeParse(result.body);
      if (!parsed.success) {
        const contractError: ApiErrorDetails = {
          kind: "UNKNOWN",
          httpStatus: result.raw.status,
          code: "CLIENT_CONTRACT_MISMATCH",
          message: "The server response did not match the audited contract.",
        };
        throw contractError;
      }
      return parsed.data;
    }

    return result.body as TResponse;
  }

  private async fetchAttempt(
    options: ApiRequestOptions<unknown>,
    correlationId: string,
    token: string | undefined,
    hasBody: boolean
  ): Promise<RawResult> {
    const headers = assembleHeaders({
      token,
      correlationId,
      idempotencyKey: options.idempotencyKey,
      hasBody,
    });

    const url = this.config.apiBaseUrl.replace(/\/+$/, "") + options.path;

    let raw: Response;
    try {
      raw = await this.fetchImpl(url, {
        method: options.method,
        headers,
        body: hasBody ? JSON.stringify(options.body) : undefined,
        signal: options.signal,
      });
    } catch (cause) {
      throw mapNetworkError(cause);
    }

    if (raw.status === 204) {
      return { ok: true, raw, body: undefined };
    }

    const text = await raw.text();
    let body: unknown = undefined;
    if (text) {
      try {
        body = JSON.parse(text);
      } catch {
        body = undefined;
      }
    }

    if (!raw.ok) {
      return { ok: false, raw, body, error: mapHttpError({ status: raw.status, body, headers: raw.headers }) };
    }

    return { ok: true, raw, body };
  }

  private signalsAuthExpired(error: ApiErrorDetails): void {
    try {
      this.authProvider?.signalAuthExpired(error);
    } catch {
      // Safe: signal handling must never crash a request boundary.
    }
  }

  private notifyAuthExpired(
    options: ApiRequestOptions<unknown>,
    error: ApiErrorDetails
  ): void {
    options.onAuthExpired?.(error);
  }
}

/** Transient refresh failures become retryable connection errors, not logout. */
function mapTransientError(error: AuthTransientError): ApiErrorDetails {
  if (error.category === "server_unavailable") {
    return {
      kind: "SERVER_ERROR",
      httpStatus: 503,
      message: error.message,
    };
  }
  return {
    kind: "NETWORK_ERROR",
    httpStatus: 0,
    message: error.message,
  };
}

/** Shared mobile-wide client. Screens go through this instance. */
export const apiClient = new ApiClient();