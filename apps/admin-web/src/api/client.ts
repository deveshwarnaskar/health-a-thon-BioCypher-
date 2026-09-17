import { z } from "zod";
import { tokenStorage } from "../auth/tokenStorage";
import { refreshAccessToken } from "../auth/oidc";
import { assertNoClinicalFields } from "../contracts";

export interface RequestOptions extends Omit<RequestInit, "body"> {
  params?: Record<string, string | number | boolean | null | undefined>;
  body?: unknown;
  skipIdempotency?: boolean;
  _retry?: boolean;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details?: Record<string, unknown>;
  readonly retryAfter?: number;

  constructor(options: {
    message: string;
    status: number;
    code: string;
    details?: Record<string, unknown>;
    retryAfter?: number;
  }) {
    super(options.message);
    this.name = "ApiError";
    this.status = options.status;
    this.code = options.code;
    this.details = options.details;
    this.retryAfter = options.retryAfter;
  }
}

// Global listener for session expiry (e.g. to redirect to login)
let sessionExpiryHandler: (() => void) | null = null;
export function setSessionExpiryHandler(handler: (() => void) | null): void {
  sessionExpiryHandler = handler;
}

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

export async function apiClient<T>(
  endpoint: string,
  schema: z.ZodType<T>,
  options: RequestOptions = {},
): Promise<T> {
  const method = (options.method || "GET").toUpperCase();
  const url = new URL(
    endpoint.startsWith("http") ? endpoint : `${BASE_URL}${endpoint}`,
    window.location.origin,
  );

  // Append query params if any
  if (options.params) {
    for (const [key, value] of Object.entries(options.params)) {
      if (value !== undefined && value !== null) {
        url.searchParams.set(key, String(value));
      }
    }
  }

  const headers = new Headers(options.headers || {});

  // Correlation ID
  if (!headers.has("X-Correlation-ID")) {
    headers.set("X-Correlation-ID", window.crypto.randomUUID());
  }

  // Idempotency Key on unsafe mutations
  const isUnsafeMutation = ["POST", "PATCH", "PUT", "DELETE"].includes(method);
  if (isUnsafeMutation && !options.skipIdempotency && !headers.has("Idempotency-Key")) {
    headers.set("Idempotency-Key", window.crypto.randomUUID());
  }

  // Authorization Header
  const token = tokenStorage.getAccessToken();
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  // Content-Type
  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const fetchOptions: RequestInit = {
    method,
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    credentials: options.credentials || "same-origin",
  };

  let response: Response;
  try {
    response = await fetch(url.toString(), fetchOptions);
  } catch (netErr) {
    throw new ApiError({
      message: netErr instanceof Error ? netErr.message : "Network error occurred",
      status: 0,
      code: "NETWORK_ERROR",
    });
  }

  // Handle 401 with single refresh + retry
  if (response.status === 401) {
    if (!options._retry) {
      const refreshToken = tokenStorage.getRefreshToken();
      if (refreshToken) {
        try {
          const newTokens = await refreshAccessToken(refreshToken);
          tokenStorage.setTokens({
            accessToken: newTokens.access_token,
            refreshToken: newTokens.refresh_token || refreshToken,
            expiresAt: Date.now() + newTokens.expires_in * 1000,
          });

          // Retry once with new token
          const retryHeaders = new Headers(options.headers || {});
          retryHeaders.set("Authorization", `Bearer ${newTokens.access_token}`);
          return apiClient(endpoint, schema, {
            ...options,
            _retry: true,
            headers: retryHeaders,
          });
        } catch {
          // Refresh failed
          tokenStorage.clearTokens();
          if (sessionExpiryHandler) sessionExpiryHandler();
          throw new ApiError({
            message: "Session expired. Please log in again.",
            status: 401,
            code: "SESSION_EXPIRED",
          });
        }
      }
    }

    // Second failure or no refresh token
    tokenStorage.clearTokens();
    if (sessionExpiryHandler) sessionExpiryHandler();
    throw new ApiError({
      message: "Authentication required or session expired.",
      status: 401,
      code: "UNAUTHENTICATED",
    });
  }

  // Handle Rate Limiting (429)
  if (response.status === 429) {
    const retryHeader = response.headers.get("Retry-After");
    const retryAfter = retryHeader ? parseInt(retryHeader, 10) : undefined;
    throw new ApiError({
      message: "Too many requests. Please slow down and try again later.",
      status: 429,
      code: "RATE_LIMITED",
      retryAfter,
    });
  }

  // Parse error responses
  if (!response.ok) {
    let errorData: unknown;
    try {
      errorData = await response.json();
    } catch {
      errorData = null;
    }

    const errorObj =
      errorData && typeof errorData === "object" && "error" in errorData
        ? (errorData as { error: { code?: string; message?: string; details?: Record<string, unknown> } }).error
        : null;

    const code = errorObj?.code || `HTTP_${response.status}`;
    const message =
      errorObj?.message ||
      (response.status === 403
        ? "Operation denied. Administrator authority required."
        : response.status === 404
        ? "Requested resource was not found."
        : response.status === 409
        ? "Resource conflict occurred."
        : response.status === 422
        ? "Validation failed on the submitted data."
        : `Server error (${response.status})`);

    throw new ApiError({
      message,
      status: response.status,
      code,
      details: errorObj?.details,
    });
  }

  // Handle successful empty response (e.g. 204)
  if (response.status === 204) {
    return schema.parse(undefined);
  }

  // Parse JSON response body
  let rawJson: unknown;
  try {
    rawJson = await response.json();
  } catch {
    throw new ApiError({
      message: "Failed to parse server response as JSON",
      status: response.status,
      code: "MALFORMED_RESPONSE",
    });
  }

  // Explicit safety assertion: zero clinical data exposure in admin console
  assertNoClinicalFields(rawJson);

  // Validate response strictly against Zod contract
  const parseResult = schema.safeParse(rawJson);
  if (!parseResult.success) {
    throw new ApiError({
      message: `Response contract violation: ${parseResult.error.message}`,
      status: response.status,
      code: "SCHEMA_VALIDATION_ERROR",
      details: { issues: parseResult.error.issues },
    });
  }

  return parseResult.data;
}

export const api = {
  get<T>(endpoint: string, schema: z.ZodType<T>, options?: RequestOptions): Promise<T> {
    return apiClient(endpoint, schema, { ...options, method: "GET" });
  },
  post<T>(endpoint: string, schema: z.ZodType<T>, body?: unknown, options?: RequestOptions): Promise<T> {
    return apiClient(endpoint, schema, { ...options, method: "POST", body });
  },
  patch<T>(endpoint: string, schema: z.ZodType<T>, body?: unknown, options?: RequestOptions): Promise<T> {
    return apiClient(endpoint, schema, { ...options, method: "PATCH", body });
  },
  delete<T>(endpoint: string, schema: z.ZodType<T>, options?: RequestOptions): Promise<T> {
    return apiClient(endpoint, schema, { ...options, method: "DELETE" });
  },
};
