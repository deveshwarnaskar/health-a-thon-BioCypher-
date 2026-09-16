export type AuthErrorCategory =
  | "configuration"
  | "network"
  | "server_unavailable"
  | "timeout"
  | "oidc_denied"
  | "oidc_canceled"
  | "unknown";

export type AccessDeniedReason =
  | "unknown_role"
  | "insufficient_capability"
  | "unlinked_identity"
  | "caregiver_revoked"
  | "caregiver_expired"
  | "facility_mismatch"
  | "deactivated"
  | "general";

export type AuthUser = {
  actor_id: string;
  tenant_id: string;
  facility_id: string | null;
  role: string | null;
  capabilities: readonly string[];
  roles: string[];
};

export type AuthFlowEvent =
  | { type: "BOOTSTRAP_COMPLETE"; hasTokens: boolean }
  | { type: "AUTH_INITIATED" }
  | { type: "AUTH_SUCCESS"; user: AuthUser; accessToken: string }
  | { type: "SESSION_EXPIRING"; error?: unknown }
  | { type: "SESSION_EXPIRED"; error?: unknown }
  | { type: "REFRESH_SUCCESS"; accessToken: string }
  | { type: "REFRESH_FAILURE"; error?: unknown }
  | { type: "LOGOUT" }
  | { type: "AUTH_ERROR"; category: AuthErrorCategory; error?: unknown }
  | { type: "ACCESS_DENIED"; reason: AccessDeniedReason; user?: AuthUser }
  | { type: "DEACTIVATED"; user?: AuthUser };

export type AuthFlowState =
  | { name: "unknown" }
  | { name: "bootstrapping" }
  | { name: "unauthenticated"; reason?: "initial" | "restored_empty" | "refresh_failed" }
  | { name: "authenticating" }
  | { name: "authenticated"; user: AuthUser; accessToken: string }
  | { name: "session_expiring"; user: AuthUser }
  | { name: "refreshing"; user: AuthUser; accessToken: string }
  | { name: "failed"; category: AuthErrorCategory; error?: unknown }
  | { name: "session_expired" }
  | { name: "access_denied"; reason: AccessDeniedReason; user?: AuthUser }
  | { name: "deactivated"; user?: AuthUser };

export const INITIAL_STATE: AuthFlowState = { name: "unknown" };

const ALLOWED: Record<AuthFlowState["name"], ReadonlySet<AuthFlowEvent["type"]>> = {
  unknown: new Set([
    "BOOTSTRAP_COMPLETE",
    "AUTH_INITIATED",
    "AUTH_SUCCESS",
    "SESSION_EXPIRED",
    "REFRESH_SUCCESS",
    "REFRESH_FAILURE",
    "AUTH_ERROR",
    "LOGOUT",
    "ACCESS_DENIED",
    "DEACTIVATED",
  ]),
  bootstrapping: new Set([
    "BOOTSTRAP_COMPLETE",
    "AUTH_SUCCESS",
    "REFRESH_SUCCESS",
    "REFRESH_FAILURE",
    "SESSION_EXPIRED",
    "AUTH_ERROR",
    "LOGOUT",
    "ACCESS_DENIED",
    "DEACTIVATED",
  ]),
  unauthenticated: new Set([
    "AUTH_INITIATED",
    "SESSION_EXPIRING",
    "SESSION_EXPIRED",
    "AUTH_ERROR",
    "LOGOUT",
    "ACCESS_DENIED",
    "DEACTIVATED",
  ]),
  authenticating: new Set([
    "AUTH_SUCCESS",
    "SESSION_EXPIRING",
    "SESSION_EXPIRED",
    "REFRESH_SUCCESS",
    "REFRESH_FAILURE",
    "AUTH_ERROR",
    "ACCESS_DENIED",
    "DEACTIVATED",
    "LOGOUT",
  ]),
  authenticated: new Set([
    "SESSION_EXPIRING",
    "SESSION_EXPIRED",
    "REFRESH_SUCCESS",
    "REFRESH_FAILURE",
    "LOGOUT",
    "ACCESS_DENIED",
    "DEACTIVATED",
  ]),
  session_expiring: new Set([
    "REFRESH_SUCCESS",
    "REFRESH_FAILURE",
    "SESSION_EXPIRED",
    "LOGOUT",
  ]),
  refreshing: new Set(["REFRESH_SUCCESS", "REFRESH_FAILURE", "SESSION_EXPIRED", "LOGOUT"]),
  failed: new Set(["AUTH_INITIATED", "LOGOUT", "AUTH_ERROR"]),
  session_expired: new Set(["AUTH_INITIATED", "SESSION_EXPIRED", "LOGOUT"]),
  access_denied: new Set(["AUTH_INITIATED", "LOGOUT"]),
  deactivated: new Set(["AUTH_INITIATED", "LOGOUT"]),
};

function assertAllowed(from: AuthFlowState["name"], event: AuthFlowEvent["type"]): void {
  if (!ALLOWED[from].has(event)) {
    throw new Error(`Auth state machine: event ${event} is not allowed from state ${from}`);
  }
}

function byEmptyUser(): AuthUser {
  return { actor_id: "", tenant_id: "", facility_id: null, role: null, capabilities: [], roles: [] };
}

export function authStateReducer(
  state: AuthFlowState,
  event: AuthFlowEvent
): AuthFlowState {
  assertAllowed(state.name, event.type);

  switch (event.type) {
    case "BOOTSTRAP_COMPLETE":
      return event.hasTokens
        ? { name: "bootstrapping" }
        : { name: "unauthenticated", reason: "initial" };

    case "AUTH_INITIATED":
      return { name: "authenticating" };

    case "AUTH_SUCCESS":
      return { name: "authenticated", user: event.user, accessToken: event.accessToken };

    case "SESSION_EXPIRING":
      if (state.name === "authenticated") {
        return { name: "session_expiring", user: state.user };
      }
      if (state.name === "authenticating" || state.name === "unauthenticated") {
        return { name: "session_expiring", user: byEmptyUser() };
      }
      return { name: "session_expiring", user: byEmptyUser() };

    case "SESSION_EXPIRED":
      if (state.name === "session_expired") return state;
      return { name: "session_expired" };

    case "REFRESH_SUCCESS":
      return { name: "authenticated", user: stateUser(state), accessToken: event.accessToken };

    case "REFRESH_FAILURE":
      return { name: "session_expired" };

    case "LOGOUT":
      return { name: "unauthenticated", reason: "initial" };

    case "AUTH_ERROR":
      return { name: "failed", category: event.category, error: event.error };

    case "ACCESS_DENIED":
      return { name: "access_denied", reason: event.reason, user: event.user };

    case "DEACTIVATED":
      return { name: "deactivated", user: event.user };
  }
}

function stateUser(state: AuthFlowState): AuthUser {
  if ("user" in state && state.user) return state.user as AuthUser;
  return byEmptyUser();
}