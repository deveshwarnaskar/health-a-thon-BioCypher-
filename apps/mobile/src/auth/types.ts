import type { AuthVerifyResponse } from "../services/schemas/auth";

/**
 * Authenticated context derived from GET /api/v2/auth/verify
 * (Gate 10A §7 JWT claims → AuthVerifyResponse).
 */
export type AuthenticatedContext = {
  actor_id: string;
  tenant_id: string;
  roles: string[];
  facility_id: string | null;
};

export type AuthStatus =
  | { state: "unknown" }
  | { state: "authenticated"; context: AuthenticatedContext }
  | { state: "anonymous" };

export function toAuthenticatedContext(verify: AuthVerifyResponse): AuthenticatedContext {
  return {
    actor_id: verify.actor_id,
    tenant_id: verify.tenant_id,
    roles: verify.roles,
    facility_id: verify.facility_id ?? null,
  };
}