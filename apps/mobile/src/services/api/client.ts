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

export type ApiDependencies = {
  config?: AppApiConfig;
  fetchImpl?: typeof fetch;
  createCorrelationId?: () => string;
};

/**
 * Single HTTP boundary for the mobile app. Centralizes:
 * - X-Correlation-ID on every request
 * - Authorization: Bearer <token> when a token is supplied
 * - Idempotency-Key on mutations
 * - typed error normalization (never leaks stack traces)
 * - auth-expired signalling on 401 for AuthSessionProvider
 *
 * Endpoint URLs are never hard-coded in callers; they come from
 * `src/services/api/endpoints/*`.
 */
export class ApiClient {
  private readonly config: AppApiConfig;
  private readonly fetchImpl: typeof fetch;
  private readonly createCorrelationId: () => string;

  constructor(deps: ApiDependencies = {}) {
    this.config = deps.config ?? getApiConfig();
    this.fetchImpl = deps.fetchImpl ?? fetch;
    this.createCorrelationId = deps.createCorrelationId ?? newCorrelationId;
  }

  async request<TResponse>(options: ApiRequestOptions<TResponse>): Promise<TResponse> {
    requireConfigured(this.config);

    const correlationId = this.createCorrelationId();
    const headers = assembleHeaders({
      token: options.token,
      correlationId,
      idempotencyKey: options.idempotencyKey,
      hasBody: options.body !== undefined,
    });

    const url = this.config.apiBaseUrl.replace(/\/+$/, "") + options.path;

    let raw: Response;
    try {
      raw = await this.fetchImpl(url, {
        method: options.method,
        headers,
        body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
        signal: options.signal,
      });
    } catch (cause) {
      throw mapNetworkError(cause);
    }

    if (raw.status === 204) {
      return undefined as TResponse;
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
      const error = mapHttpError({ status: raw.status, body, headers: raw.headers });
      if (isAuthExpiredSignal(error)) {
        options.onAuthExpired?.(error);
      }
      throw error;
    }

    if (options.schema) {
      const parsed = options.schema.safeParse(body);
      if (!parsed.success) {
        const contractError: ApiErrorDetails = {
          kind: "UNKNOWN",
          httpStatus: raw.status,
          code: "CLIENT_CONTRACT_MISMATCH",
          message: "The server response did not match the audited contract.",
        };
        throw contractError;
      }
      return parsed.data;
    }

    return body as TResponse;
  }
}

/** Shared mobile-wide client. Screens go through this instance. */
export const apiClient = new ApiClient();