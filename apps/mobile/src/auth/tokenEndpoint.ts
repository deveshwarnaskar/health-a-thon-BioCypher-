/**
 * OIDC token-endpoint error classification.
 *
 * The token endpoint is called with explicit fetch so HTTP status and the
 * RFC 6749 `error` code survive. That distinction is what keeps a transient
 * 5xx/network blip from destroying a still-valid refresh token, while an
 * `invalid_grant` correctly terminates the session.
 */

export class TokenEndpointError extends Error {
  constructor(
    message: string,
    public readonly httpStatus: number,
    public readonly errorCode?: string
  ) {
    super(message);
    this.name = "TokenEndpointError";
  }
}

export class TokenNetworkError extends Error {
  constructor(public readonly cause?: unknown) {
    super("The OIDC token endpoint could not be reached.");
    this.name = "TokenNetworkError";
  }
}

export type TransientCategory = "network" | "server_unavailable" | "timeout";

/** Thrown by the session manager when a refresh could NOT complete for a
 * transient reason (network/server). The session is preserved and MUST NOT be
 * treated as expired — the UI shows a retryable connection error instead. */
export class AuthTransientError extends Error {
  constructor(public readonly category: TransientCategory, cause?: unknown) {
    super(
      category === "network"
        ? "Network is unreachable. Please check your connection."
        : "The authentication service is temporarily unavailable. Please try again."
    );
    this.name = "AuthTransientError";
    if (cause) (this as { cause?: unknown }).cause = cause;
  }
}

export type TokenEndpointStatus = "ok" | "invalid_session_input" | "transient_failure";

/** Categorizes a refresh-token exchange outcome:
 * - "transient": network/5xx/429/ambiguous → session preserved, retryable.
 * - "invalid_session_input": invalid_grant/unauthorized_client/etc → the
 *   refresh token is no longer usable; the session MUST be cleared.
 * - "ok": the refresh succeeded. */
export function classifyRefreshOutcome(error: unknown): "transient" | "invalid_session_input" {
  if (error instanceof TokenNetworkError) return "transient";

  if (error instanceof TokenEndpointError) {
    if (error.httpStatus >= 500) return "transient";
    if (error.httpStatus === 429) return "transient";

    switch (error.errorCode) {
      case "invalid_grant":
      case "invalid_client":
      case "unauthorized_client":
      case "invalid_request":
        return "invalid_session_input";
      default:
        return "invalid_session_input";
    }
  }

  return "invalid_session_input";
}