import type { AuthenticatedContext } from "./types";
import { roleFromAuthRoles, type Role } from "../authz/roles";
import { capabilitiesForRole } from "../authz/capabilities";
import type { AuthUser } from "./authStateMachine";

/**
 * Builds the client-safe AuthUser from the backend-verified
 * AuthenticatedContext (GET /api/v2/auth/verify).  The role is derived
 * client-side via the capability catalog; the backend remains authoritative
 * at request time.
 */
export function buildAuthUser(ctx: AuthenticatedContext): AuthUser {
  const role: Role | null = roleFromAuthRoles(ctx.roles);
  return {
    actor_id: ctx.actor_id,
    tenant_id: ctx.tenant_id,
    facility_id: ctx.facility_id ?? null,
    roles: [...ctx.roles],
    role,
    capabilities: role ? [...capabilitiesForRole(role)] : [],
  };
}
