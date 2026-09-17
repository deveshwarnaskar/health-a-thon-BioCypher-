import { z } from "zod";

// ─── Patient-facing observation feed (verified contract) ─────────────────
// Patient-facing responses MUST NOT contain carbs_grams or glycemic_index
// (Gate 10A §13 information-asymmetry invariant).

export const patientGlucoseObservationSchema = z
  .object({
    kind: z.literal("glucose"),
    value_mg_dl: z.number().int().nullable().optional(),
    tag: z.string().nullable().optional(),
    taken_at: z.string(),
    confirmed: z.boolean(),
  })
  .strict();

export const patientMealObservationSchema = z
  .object({
    kind: z.literal("meal"),
    description: z.string(),
    portion_label: z.string().nullable().optional(),
    quantity: z.number().nullable().optional(),
    recorded_at: z.string(),
    confirmed: z.boolean(),
  })
  .strict();

export const patientObservationFeedSchema = z
  .object({
    patient_id: z.string(),
    items: z.array(
      z.union([patientGlucoseObservationSchema, patientMealObservationSchema]),
    ),
  })
  .strict();

export type PatientObservationFeedResponse = z.infer<typeof patientObservationFeedSchema>;
export type PatientGlucoseObservation = z.infer<typeof patientGlucoseObservationSchema>;
export type PatientMealObservation = z.infer<typeof patientMealObservationSchema>;

// ─── Glucose ingestion (verified contract) ───────────────────────────────

export const READING_TAGS = [
  "fasting",
  "premeal",
  "postbreakfast",
  "postlunch",
  "postdinner",
] as const;

export type ReadingTag = (typeof READING_TAGS)[number];

export const readingTagSchema = z.enum(READING_TAGS);

export const READING_TAG_LABELS: Record<ReadingTag, string> = {
  fasting: "Fasting",
  premeal: "Pre-meal",
  postbreakfast: "Post-breakfast",
  postlunch: "Post-lunch",
  postdinner: "Post-dinner",
};

export const ingestGlucoseRequestSchema = z
  .object({
    patient_id: z.string().uuid(),
    value_mg_dl: z.number().int().min(20).max(600),
    tag: z.string().nullable().optional(),
    taken_at: z.string().optional(),
  })
  .strict();

export type IngestGlucoseRequest = z.infer<typeof ingestGlucoseRequestSchema>;

export const glucoseFormInputSchema = z.object({
  value_mg_dl: z.union([
    z
      .number()
      .int("Reading must be a whole number.")
      .min(20, "Reading must be at least 20 mg/dL.")
      .max(600, "Reading must be at most 600 mg/dL."),
    z
      .string()
      .min(1, "Please enter a glucose reading.")
      .refine((val) => {
        const num = Number(val);
        return !Number.isNaN(num) && Number.isInteger(num);
      }, "Reading must be a whole number.")
      .refine((val) => Number(val) >= 20, "Reading must be at least 20 mg/dL.")
      .refine((val) => Number(val) <= 600, "Reading must be at most 600 mg/dL."),
  ]),
  tag: readingTagSchema.nullable().optional(),
  taken_at: z.string().optional(),
});

export type GlucoseFormInput = z.infer<typeof glucoseFormInputSchema>;

export const ingestGlucoseResponseSchema = z
  .object({
    observation_id: z.string(),
    patient_id: z.string(),
    value_mg_dl: z.number().int(),
    taken_at: z.string(),
  })
  .strict();

export type IngestGlucoseResponse = z.infer<typeof ingestGlucoseResponseSchema>;

// ─── Clinician-only surface (NOT exposed by any verified endpoint today) ─
// Exists to document the asymmetry boundary; patient-facing screens must
// never request or render these fields.

export const clinicalMealObservationSchema = z
  .object({
    kind: z.literal("meal"),
    observation_id: z.string(),
    description: z.string(),
    portion_label: z.string().nullable().optional(),
    quantity: z.number().nullable().optional(),
    carbs_grams: z.number().nullable().optional(),
    glycemic_index: z.string().nullable().optional(),
    recorded_at: z.string(),
    confirmation: z.string(),
  })
  .strict();

export const PATIENT_FACING_FORBIDDEN_FIELDS = ["carbs_grams", "glycemic_index"] as const;