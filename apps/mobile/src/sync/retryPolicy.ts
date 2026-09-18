import type { ApiErrorDetails } from "../services/api/errors";

export type RetryClassification =
  | { outcome: "RETRYABLE"; delayMs: number; code: string; message: string }
  | { outcome: "PERMANENT_REJECTION"; code: string; message: string }
  | { outcome: "CONFLICT"; code: string; message: string }
  | { outcome: "AUTH_EXPIRED"; code: string; message: string };

export function classifySyncError(
  error: unknown,
  attemptCount: number,
  responseHeaders?: Headers | Record<string, string>
): RetryClassification {
  const details = error as Partial<ApiErrorDetails> | undefined;
  const httpStatus = details?.httpStatus;
  const code = details?.code ?? "UNKNOWN_ERROR";
  const message = details?.message ?? "An unexpected sync error occurred.";

  // 1. HTTP 429 - Rate Limit
  if (httpStatus === 429) {
    let delayMs = 5000;
    if (responseHeaders) {
      const retryAfter =
        typeof (responseHeaders as Headers).get === "function"
          ? (responseHeaders as Headers).get("retry-after")
          : (responseHeaders as Record<string, string>)["retry-after"];
      if (retryAfter) {
        const seconds = parseInt(retryAfter, 10);
        if (!isNaN(seconds) && seconds > 0) {
          delayMs = seconds * 1000;
        }
      }
    }
    return {
      outcome: "RETRYABLE",
      delayMs,
      code: "RATE_LIMITED",
      message: "Server busy. Sync will retry shortly.",
    };
  }

  // 2. HTTP 401 - Unauthorized after refresh failure
  if (httpStatus === 401) {
    return {
      outcome: "AUTH_EXPIRED",
      code: "SESSION_EXPIRED",
      message: "Session expired. Re-authentication required.",
    };
  }

  // 3. HTTP 403 - Forbidden (Revoked relationship, deactivated patient, unauthorized role)
  if (httpStatus === 403) {
    return {
      outcome: "PERMANENT_REJECTION",
      code: "AUTHORIZATION_REVOKED",
      message: "Permission denied or authorization has been revoked.",
    };
  }

  // 4. HTTP 404 - Not Found
  if (httpStatus === 404) {
    return {
      outcome: "PERMANENT_REJECTION",
      code: "RESOURCE_NOT_FOUND",
      message: "Target resource does not exist.",
    };
  }

  // 5. HTTP 422 - Validation Failure
  if (httpStatus === 422) {
    return {
      outcome: "PERMANENT_REJECTION",
      code: "VALIDATION_FAILED",
      message: "Payload rejected by server schema validation.",
    };
  }

  // 6. HTTP 409 - Conflict (Idempotency mismatch or state conflict)
  if (httpStatus === 409) {
    return {
      outcome: "CONFLICT",
      code: "STATE_CONFLICT",
      message: "Conflict detected with current server state.",
    };
  }

  // 7. HTTP 5xx - Server Errors
  if (httpStatus && httpStatus >= 500 && httpStatus <= 599) {
    const delayMs = calculateExponentialBackoff(attemptCount);
    return {
      outcome: "RETRYABLE",
      delayMs,
      code: "SERVER_ERROR",
      message: "Server error encountered. Will retry.",
    };
  }

  // 8. Network drops, timeouts, offline
  if (details?.kind === "NETWORK_ERROR" || !httpStatus) {
    const delayMs = calculateExponentialBackoff(attemptCount);
    return {
      outcome: "RETRYABLE",
      delayMs,
      code: "NETWORK_UNAVAILABLE",
      message: "Network unreachable. Sync queued for reconnect.",
    };
  }

  // Default: permanent rejection to avoid infinite loops on unknown client errors
  return {
    outcome: "PERMANENT_REJECTION",
    code,
    message,
  };
}

function calculateExponentialBackoff(attempt: number): number {
  const safeAttempt = typeof attempt === "number" && !isNaN(attempt) ? attempt : 0;
  const baseMs = 1000;
  const maxMs = 60000;
  const jitter = Math.floor(Math.random() * 500);
  const exponential = Math.min(baseMs * Math.pow(2, safeAttempt), maxMs);
  return exponential + jitter;
}
