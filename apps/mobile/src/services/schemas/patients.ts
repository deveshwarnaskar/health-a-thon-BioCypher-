import { z } from "zod";

// ─── Clinician patient cohort (Gate 10F-B contract → Gate 10F-M) ──────────
// Mirrors models.py:PatientSummaryResponse / PatientListResponse. Identity +
// lifecycle facts ONLY — no observations, no medication guidance, no AI-review
// artifacts, no audit or internal fields. Deliberately excludes phone.
// `uh_id` is the unhashed internal identifier for the authenticated member's
// cohort read; it never leaks through the patient/caregiver-facing surfaces.

export const patientSummaryResponseSchema = z
  .object({
    patient_id: z.string(),
    uh_id: z.string(),
    name: z.string(),
    facility_id: z.string().nullable().optional(),
    active: z.boolean(),
    created_at: z.string(),
  })
  .strict();

export type PatientSummaryResponse = z.infer<typeof patientSummaryResponseSchema>;

export const patientListResponseSchema = z
  .object({
    patient_count: z.number().int(),
    items: z.array(patientSummaryResponseSchema),
  })
  .strict();

export type PatientListResponse = z.infer<typeof patientListResponseSchema>;