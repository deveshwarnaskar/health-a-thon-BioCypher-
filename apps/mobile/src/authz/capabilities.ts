import type { Role } from "./roles";

/**
 * Capability catalog aligned with the backend authorization matrix
 * (Gate 10A §8 / API contract inventory §6). The backend policy is the
 * authority at request time; these maps only decide UI composition and
 * placeholders in Gate 10B.
 */
export const CAPABILITIES = [
  "READ_OBSERVATIONS",
  "WRITE_OBSERVATIONS",
  "READ_GLUCOSE",
  "READ_MEAL",
  "CREATE_GLUCOSE",
  "CREATE_MEAL",
  "READ_MEDICATION_PLANS",
  "WRITE_MEDICATION_PLANS",
  "READ_AI_ARTIFACT",
  "REVIEW_AI_ARTIFACT",
  "READ_PATIENT",
  "WRITE_PATIENT",
  "MANAGE_CAREGIVER_RELATIONSHIPS",
] as const;

export type Capability = (typeof CAPABILITIES)[number];

export const CAPABILITY_BY_ROLE: Record<Role, readonly Capability[]> = {
  Patient: ["READ_OBSERVATIONS", "WRITE_OBSERVATIONS", "READ_PATIENT"],
  Caregiver: ["READ_GLUCOSE", "READ_MEAL", "CREATE_GLUCOSE", "CREATE_MEAL"],
  Doctor: [
    "READ_OBSERVATIONS",
    "WRITE_OBSERVATIONS",
    "READ_MEDICATION_PLANS",
    "WRITE_MEDICATION_PLANS",
    "READ_AI_ARTIFACT",
    "REVIEW_AI_ARTIFACT",
    "READ_PATIENT",
    "WRITE_PATIENT",
  ],
  Nurse: [
    "READ_OBSERVATIONS",
    "WRITE_OBSERVATIONS",
    "READ_MEDICATION_PLANS",
    "WRITE_MEDICATION_PLANS",
    "READ_AI_ARTIFACT",
    "REVIEW_AI_ARTIFACT",
    "READ_PATIENT",
  ],
  CareCoordinator: [
    "READ_OBSERVATIONS",
    "READ_MEDICATION_PLANS",
    "READ_AI_ARTIFACT",
    "READ_PATIENT",
    "WRITE_PATIENT",
    "MANAGE_CAREGIVER_RELATIONSHIPS",
  ],
  Dietitian: [
    "READ_OBSERVATIONS",
    "WRITE_OBSERVATIONS",
    "READ_MEDICATION_PLANS",
    "WRITE_MEDICATION_PLANS",
    "READ_AI_ARTIFACT",
    "REVIEW_AI_ARTIFACT",
    "READ_PATIENT",
  ],
  FieldHealthWorker: ["READ_OBSERVATIONS", "WRITE_OBSERVATIONS", "READ_PATIENT"],
};

export function capabilitiesForRole(role: Role): readonly Capability[] {
  return CAPABILITY_BY_ROLE[role];
}

export function can(role: Role, capability: Capability): boolean {
  return CAPABILITY_BY_ROLE[role].includes(capability);
}