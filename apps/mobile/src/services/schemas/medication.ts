import { z } from "zod";

// ─── Medication plan (verified contract) ─────────────────────────────────
// Mirrors models.py:CreateMedicationPlanRequest/Response + MedicationPlanResponse.

export const createMedicationPlanRequestSchema = z
  .object({
    patient_id: z.string().uuid(),
    medication: z.string().min(1),
    instruction: z.string().optional(),
  })
  .strict();

export type CreateMedicationPlanRequest = z.infer<typeof createMedicationPlanRequestSchema>;

export const createMedicationPlanResponseSchema = z
  .object({
    medication_plan_id: z.string(),
    patient_id: z.string(),
  })
  .strict();

export type CreateMedicationPlanResponse = z.infer<typeof createMedicationPlanResponseSchema>;

export const medicationPlanResponseSchema = z
  .object({
    medication_plan_id: z.string(),
    patient_id: z.string(),
    medication: z.string(),
    instruction: z.string(),
    active: z.boolean(),
    prescribed_by_role: z.string(),
    created_at: z.string(),
  })
  .strict();

export type MedicationPlanResponse = z.infer<typeof medicationPlanResponseSchema>;

export const medicationPlanListResponseSchema = z
  .object({
    plan_count: z.number().int(),
    items: z.array(medicationPlanResponseSchema),
  })
  .strict();

export type MedicationPlanListResponse = z.infer<typeof medicationPlanListResponseSchema>;