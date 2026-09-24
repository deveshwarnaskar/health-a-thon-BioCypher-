import { z } from "zod";

// ─── Caregiver patient discovery (Gate 10E-B contract → Gate 10E-M) ──────
// PHI-minimal relational patient list. Carries identifiers and relationship
// facts ONLY — never clinical analytics (no glucose values, no risk scores,
// no treatment or medication-plan content). Mirrors the backend response model
// `CaregiverPatientListResponse` (strict schema, extra="forbid").

/** Verbatim capability tokens returned by the relationship (backend). */
export const CAREGIVER_CAPABILITIES = [
  "read_glucose",
  "create_glucose",
  "read_meal",
  "create_meal",
  "read_medication_events",
  "create_medication_events",
  "read_care_tasks",
  "complete_care_tasks",
] as const;

export type CaregiverCapability = (typeof CAREGIVER_CAPABILITIES)[number];

export const caregiverCapabilitySchema = z.enum(CAREGIVER_CAPABILITIES);

export const caregiverPatientListItemSchema = z
  .object({
    relationship_id: z.string(),
    patient_id: z.string(),
    relationship_label: z.string().min(1),
    status: z.literal("verified"),
    capabilities: z.array(caregiverCapabilitySchema),
    expires_at: z.string().nullable().optional(),
    name: z.string().min(1),
  })
  .strict();

export const caregiverPatientListSchema = z
  .object({
    patient_count: z.number().int(),
    items: z.array(caregiverPatientListItemSchema),
  })
  .strict();

export type CaregiverPatientListItem = z.infer<typeof caregiverPatientListItemSchema>;
export type CaregiverPatientListResponse = z.infer<typeof caregiverPatientListSchema>;

// ─── UI capability gates (verbatim backend tokens, never invented) ────────

/** Completeness gate used by Gate 08: caregiver glucose read needs the pair. */
export const GLUCOSE_READ_CAPABILITIES: readonly CaregiverCapability[] = [
  "read_glucose",
  "read_meal",
];

export const GLUCOSE_WRITE_CAPABILITY: CaregiverCapability = "create_glucose";

export function canReadCaregiverGlucose(capabilities: readonly string[]): boolean {
  return GLUCOSE_READ_CAPABILITIES.every((capability) => capabilities.includes(capability));
}

export function canRecordCaregiverGlucose(capabilities: readonly string[]): boolean {
  return capabilities.includes(GLUCOSE_WRITE_CAPABILITY);
}

export const MEAL_WRITE_CAPABILITY: CaregiverCapability = "create_meal";

export function canRecordCaregiverMeal(capabilities: readonly string[]): boolean {
  return capabilities.includes(MEAL_WRITE_CAPABILITY);
}

export const CARE_TASKS_READ_CAPABILITY: CaregiverCapability = "read_care_tasks";
export const CARE_TASKS_COMPLETE_CAPABILITY: CaregiverCapability = "complete_care_tasks";

export function canReadCaregiverTasks(capabilities: readonly string[]): boolean {
  return capabilities.includes(CARE_TASKS_READ_CAPABILITY);
}

export function canCompleteCaregiverTasks(capabilities: readonly string[]): boolean {
  return capabilities.includes(CARE_TASKS_COMPLETE_CAPABILITY);
}

export const linkCaregiverPatientRequestSchema = z
  .object({
    uhid: z.string().min(2),
    relationship_label: z.string().min(1),
  })
  .strict();

export type LinkCaregiverPatientRequest = z.infer<typeof linkCaregiverPatientRequestSchema>;