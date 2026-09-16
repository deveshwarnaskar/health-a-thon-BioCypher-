/**
 * Typed HTTP error model for the API client (Gate 10A §9 / §8).
 *
 * Every failure is normalised into a safe, structured ApiError. Stack traces,
 * internals and secrets are NEVER exposed (Gate 10A §17). Backend error
 * bodies follow the shape `{ "error": { code, message, correlation_id } }`
 * (backend/interfaces/http/errors.py).
 */

import { HEADER_RETRY_AFTER } from "./headers";

export type ApiErrorKind =
  | "INVALID_REQUEST"
  | "UNAUTHORIZED"
  | "FORBIDDEN"
  | "NOT_FOUND"
  | "VALIDATION_ERROR"
  | "CONFLICT"
  | "PAYLOAD_TOO_LARGE"
  | "RATE_LIMITED"
  | "SERVER_ERROR"
  | "NETWORK_ERROR"
  | "UNKNOWN";

/**
 * Structured reason for 403s so UI can render context-aware denial messages
 * (Gate 10A §8): unlinked identity, revoked/expired caregiver relationship,
 * facility mismatch, or insufficient capability.
 */
export type ForbiddenReason =
  | "unlinked_identity"
  | "revoked_relationship"
  | "expired_relationship"
  | "facility_mismatch"
  | "insufficient_capability"
  | "authorization_denied";

/** 409 conflict subtypes surfaced by Gate 09 idempotency middleware and v2 routes. */
export type ConflictSubtype =
  | "CONCURRENT_REQUEST_IN_PROGRESS"
  | "IDEMPOTENCY_KEY_MISMATCH"
  | "INVALID_STATE"
  | "IDENTITY_MAPPING_CONFLICT"
  | "CAREGIVER_RELATIONSHIP_CONFLICT"
  | "GENERIC";

export type ApiErrorDetails = {
  kind: ApiErrorKind;
  httpStatus: number;
  code?: string;
  message: string;
  correlationId?: string;
  forbiddenReason?: ForbiddenReason;
  conflictSubtype?: ConflictSubtype;
  /** Present for 429 responses; parsed from the Retry-After header. */
  retryAfterSeconds?: number;
  /** Field-level problems for 422 responses (mapped to RHF+Zod in later gates). */
  fieldErrors?: Record<string, string[]>;
  cause?: unknown;
};

/**
 * 401 responses are a single, observable "auth-expired" signal consumed by
 * AuthSessionProvider (Gate 10C wires token handling; nothing is faked here).
 */
export type AuthExpiredSignalError = ApiErrorDetails & {
  kind: "UNAUTHORIZED";
  httpStatus: 401;
};

export function isAuthExpiredSignal(error: ApiErrorDetails): error is AuthExpiredSignalError {
  return error.kind === "UNAUTHORIZED" && error.httpStatus === 401;
}

const STATUS_KIND: Partial<Record<number, ApiErrorKind>> = {
  400: "INVALID_REQUEST",
  401: "UNAUTHORIZED",
  403: "FORBIDDEN",
  404: "NOT_FOUND",
  409: "CONFLICT",
  413: "PAYLOAD_TOO_LARGE",
  422: "VALIDATION_ERROR",
  429: "RATE_LIMITED",
  500: "SERVER_ERROR",
  502: "SERVER_ERROR",
  503: "SERVER_ERROR",
  504: "SERVER_ERROR",
};

const CONFLICT_CODE_TO_SUBTYPE: Record<string, ConflictSubtype> = {
  CONCURRENT_REQUEST_IN_PROGRESS: "CONCURRENT_REQUEST_IN_PROGRESS",
  IDEMPOTENCY_KEY_MISMATCH: "IDEMPOTENCY_KEY_MISMATCH",
  INVALID_STATE: "INVALID_STATE",
  IDENTITY_MAPPING_CONFLICT: "IDENTITY_MAPPING_CONFLICT",
  CAREGIVER_RELATIONSHIP_CONFLICT: "CAREGIVER_RELATIONSHIP_CONFLICT",
};

function forbiddenReasonForCode(code: string | undefined): ForbiddenReason {
  switch (code) {
    case "MEDICATION_PLAN_UNAUTHORIZED":
    case "REVIEW_UNAUTHORIZED":
      return "insufficient_capability";
    default:
      return "authorization_denied";
  }
}

/** Backend error envelope `{ error: { code, message, correlation_id } }`. */
export type BackendErrorBody = {
  error?: {
    code?: string;
    message?: string;
    correlation_id?: string;
    [key: string]: unknown;
  };
};

export function parseBackendErrorBody(body: unknown): BackendErrorBody["error"] | undefined {
  if (typeof body !== "object" || body === null) {
    return undefined;
  }
  const wrapped = (body as BackendErrorBody).error;
  if (typeof wrapped !== "object" || wrapped === null) {
    return undefined;
  }
  return wrapped as BackendErrorBody["error"];
}

const HTTP_DATE = /^[A-Za-z]{3},\s\d{2}\s[A-Za-z]{3}\s\d{4}\s\d{2}:\d{2}:\d{2}/;

/** RFC 7231 Retry-After: HTTP-date or integer delay-seconds. */
export function parseRetryAfter(headerValue: string | null, now: Date = new Date()): number | undefined {
  if (!headerValue) {
    return undefined;
  }
  const trimmed = headerValue.trim();
  if (/^(?:[1-9][0-9]*)$/.test(trimmed)) {
    return Number(trimmed);
  }
  // Only accept real HTTP-date values; anything else is ignored so values
  // like "-5" never resolve through lenient Date.parse heuristics.
  if (!HTTP_DATE.test(trimmed)) {
    return undefined;
  }
  const date = Date.parse(trimmed);
  if (!Number.isNaN(date)) {
    return Math.max(0, Math.ceil((date - now.getTime()) / 1000));
  }
  return undefined;
}

export type HttpErrorContext = {
  status: number;
  body?: unknown;
  headers?: Headers;
  cause?: unknown;
};

const SAFE_MESSAGE = "The request could not be completed. Please try again.";

/**
 * Backend messages are sanitized server-side, but defense-in-depth: anything
 * shaped like a stack trace / internal error is replaced with the safe copy
 * so no traceback or exception text is ever echoed to UI (Gate 10A §17).
 */
function safeMessage(raw: string | undefined): string {
  if (!raw) {
    return SAFE_MESSAGE;
  }
  if (/(traceback| stack )/i.test(raw) || /\n/.test(raw) || /\b\w+Error\b/.test(raw)) {
    return SAFE_MESSAGE;
  }
  return raw;
}

export function mapHttpError(context: HttpErrorContext): ApiErrorDetails {
  const { status, body, headers, cause } = context;
  const backendError = parseBackendErrorBody(body);
  const code = backendError?.code;
  const message = safeMessage(backendError?.message);

  const details: ApiErrorDetails = {
    kind: STATUS_KIND[status] ?? "UNKNOWN",
    httpStatus: status,
    code,
    message,
    correlationId: backendError?.correlation_id,
    cause,
  };

  if (status === 401) {
    // Auth-expired signal (AUTHENTICATION_EXPIRED, AUTHENTICATION_INVALID,
    // JWT_SIGNATURE_INVALID, AUTHENTICATION_REQUIRED all collapse here).
    return details as AuthExpiredSignalError;
  }

  if (status === 403) {
    details.forbiddenReason = forbiddenReasonForCode(code);
  }

  if (status === 409) {
    details.conflictSubtype = code ? (CONFLICT_CODE_TO_SUBTYPE[code] ?? "GENERIC") : "GENERIC";
  }

  if (status === 422) {
    const fields = (backendError?.field_errors ??
      backendError?.fields ??
      backendError?.details) as Record<string, unknown> | undefined;
    if (fields && typeof fields === "object") {
      details.fieldErrors = Object.fromEntries(
        Object.entries(fields).map(([key, value]) => [
          key,
          Array.isArray(value) ? value.map(String) : [String(value)],
        ]),
      );
    }
  }

  if (status === 429) {
    const retryAfterSeconds = parseRetryAfter(headers?.get(HEADER_RETRY_AFTER) ?? null);
    if (retryAfterSeconds !== undefined) {
      details.retryAfterSeconds = retryAfterSeconds;
    }
  }

  return details;
}

/** A fetch rejection (offline/DNS/timeout) is normalised into NETWORK_ERROR. */
export function mapNetworkError(cause: unknown): ApiErrorDetails {
  return {
    kind: "NETWORK_ERROR",
    httpStatus: 0,
    message: "Network is unreachable. Please check your connection.",
    cause,
  };
}

/** Safe helper for consumers that only need a user-facing message. */
export function toUserMessage(error: ApiErrorDetails): string {
  return error.message || SAFE_MESSAGE;
}