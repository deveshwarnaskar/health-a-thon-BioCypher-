/**
 * Platform roles (Gate 10A §8). ROLE identity is distinct from CAPABILITY:
 * a role names who you are; capabilities enumerate what the backend allows.
 * The backend is authoritative — these lists only drive UI composition.
 */

export const ROLES = [
  "Patient",
  "Caregiver",
  "Doctor",
  "Nurse",
  "CareCoordinator",
  "Dietitian",
  "FieldHealthWorker",
] as const;

export type Role = (typeof ROLES)[number];

export type RoleMode = Role | null;

/** Canonical hyphens/generalizations accepted by backend authz (roles.py). */
const BACKEND_ROLE_TOKENS: Record<Role, string[]> = {
  Patient: ["patient"],
  Caregiver: ["caregiver"],
  Doctor: ["doctor"],
  Nurse: ["nurse"],
  CareCoordinator: ["care_coordinator", "care coordinator", "carecoordinator"],
  Dietitian: ["dietitian", "dietitian/diabetes educator", "diabetes_educator"],
  FieldHealthWorker: ["field_health_worker", "field health worker", "fieldhealthworker"],
};

const TOKEN_TO_ROLE = new Map<string, Role>();
for (const [role, tokens] of Object.entries(BACKEND_ROLE_TOKENS)) {
  for (const token of tokens) {
    TOKEN_TO_ROLE.set(token, role as Role);
  }
}

/**
 * Resolves the primary platform role from AuthVerify roles. Compares against
 * exact backend tokens only; unknown strings never map (no takeover).
 */
export function roleFromAuthRoles(roles: string[]): Role | null {
  const normalized = new Set(roles.map((role) => role.trim().toLowerCase()));
  for (const token of TOKEN_TO_ROLE.keys()) {
    if (normalized.has(token)) {
      return TOKEN_TO_ROLE.get(token)!;
    }
  }
  return null;
}

export function roleLabel(role: Role): string {
  const labels: Record<Role, string> = {
    Patient: "Patient",
    Caregiver: "Caregiver",
    Doctor: "Doctor",
    Nurse: "Nurse",
    CareCoordinator: "Care Coordinator",
    Dietitian: "Dietitian",
    FieldHealthWorker: "Field Health Worker",
  };
  return labels[role];
}