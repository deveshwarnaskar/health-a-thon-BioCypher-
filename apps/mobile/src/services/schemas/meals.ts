import { z } from "zod";

/**
 * Aahaar canonical volumetric portions (Gate 10H-B).
 * Standard Indian household katori volumes in ml.
 */
export const KATORI_VOLUMES = [150, 220, 350] as const;
export type KatoriVolumeMl = (typeof KATORI_VOLUMES)[number];

export const katoriVolumeSchema = z.union([
  z.literal(150),
  z.literal(220),
  z.literal(350),
]);

export const KATORI_PORTION_LABELS: Record<KatoriVolumeMl, string> = {
  150: "Small (150 ml)",
  220: "Medium (220 ml)",
  350: "Large (350 ml)",
};

export const KATORI_SIZE_NAMES: Record<KatoriVolumeMl, string> = {
  150: "small",
  220: "medium",
  350: "large",
};

/**
 * Volumetric portion specification.
 * Strictly enforces food key, katori volume class, and quantity factor.
 */
export const mealPortionRequestSchema = z
  .object({
    food_key: z.string().min(1),
    katori_volume_ml: katoriVolumeSchema,
    quantity: z.number().min(0.1).max(100),
  })
  .strict();

export type MealPortionRequest = z.infer<typeof mealPortionRequestSchema>;

/**
 * Draft a meal observation (POST /api/v2/clinical/meals).
 * Description and patient UUID are required; portion is structured.
 */
export const logMealRequestSchema = z
  .object({
    patient_id: z.string().uuid(),
    description: z.string().min(1),
    portion: mealPortionRequestSchema.nullable().optional(),
    recorded_at: z.string().nullable().optional(),
  })
  .strict();

export type LogMealRequest = z.infer<typeof logMealRequestSchema>;

/**
 * Response from drafting a meal observation.
 * Intentionally carries NO carbohydrates or glycemic index.
 */
export const logMealResponseSchema = z
  .object({
    meal_observation_id: z.string(),
    patient_id: z.string(),
    portion_label: z.string().nullable().optional(),
    quantity: z.number().nullable().optional(),
  })
  .strict();

export type LogMealResponse = z.infer<typeof logMealResponseSchema>;

/**
 * Confirm or correct a pending meal observation (POST /api/v2/clinical/meals/{id}/confirm).
 * Patient confirmation authority only.
 */
export const confirmMealRequestSchema = z
  .object({
    corrected_description: z.string().nullable().optional(),
    corrected_portion: mealPortionRequestSchema.nullable().optional(),
  })
  .strict();

export type ConfirmMealRequest = z.infer<typeof confirmMealRequestSchema>;

/**
 * Response confirming a meal observation.
 */
export const confirmMealResponseSchema = z
  .object({
    meal_observation_id: z.string(),
    patient_id: z.string(),
    confirmation: z.string(),
  })
  .strict();

export type ConfirmMealResponse = z.infer<typeof confirmMealResponseSchema>;
