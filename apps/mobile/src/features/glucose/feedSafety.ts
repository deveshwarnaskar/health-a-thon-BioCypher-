import {
  PATIENT_FACING_FORBIDDEN_FIELDS,
  type PatientObservationFeedResponse,
} from "../../services/schemas/clinical";

/**
 * Information-asymmetry guard (Gate 10A §13 + Gate 10D).
 *
 * The patient-facing feed must NEVER expose clinician-only analytics
 * (carbs_grams, glycemic_index). The Zod schema already rejects those fields
 * with `.strict()`, but defense-in-depth: any feed response that slips a
 * forbidden field through is refused before it can reach a patient screen.
 */

export function isPatientSafeObservation(item: unknown): boolean {
  if (typeof item !== "object" || item === null) return false;
  const record = item as Record<string, unknown>;
  return PATIENT_FACING_FORBIDDEN_FIELDS.every((field) => !(field in record));
}

export function assertPatientSafeFeed(
  response: PatientObservationFeedResponse,
): PatientObservationFeedResponse {
  if (!response.items.every(isPatientSafeObservation)) {
    throw new Error("Patient-facing feed contained clinician-only fields.");
  }
  return response;
}