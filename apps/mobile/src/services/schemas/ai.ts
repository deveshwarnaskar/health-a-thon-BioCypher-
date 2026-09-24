import { z } from "zod";

// ─── AI artifact generation and review (verified contract) ───────────────────
// Mirrors models.py:GenerateAIArtifactRequest/Response & ReviewAIArtifactRequest/Response.

export const generateAiArtifactRequestSchema = z
  .object({
    patient_id: z.string(),
    context: z.string().optional(),
    task_type: z.string().optional(),
  })
  .strict();

export type GenerateAIArtifactRequest = z.infer<typeof generateAiArtifactRequestSchema>;

export const generateAiArtifactResponseSchema = z
  .object({
    artifact_id: z.string(),
    patient_id: z.string(),
    state: z.string(),
    summary: z.string(),
    model_name: z.string().nullable().optional(),
    evidence_hash: z.string().nullable().optional(),
  })
  .strict();

export type GenerateAIArtifactResponse = z.infer<typeof generateAiArtifactResponseSchema>;

export const reviewAiArtifactRequestSchema = z
  .object({
    decision: z.enum(["approve", "edit", "reject"]),
    edited_summary: z.string().nullable().optional(),
  })
  .strict();

export type ReviewAIArtifactRequest = z.infer<typeof reviewAiArtifactRequestSchema>;

export const reviewAiArtifactResponseSchema = z
  .object({
    artifact_id: z.string(),
    state: z.string(),
    reviewed_by_user_id: z.string(),
  })
  .strict();

export type ReviewAIArtifactResponse = z.infer<typeof reviewAiArtifactResponseSchema>;

export const aiArtifactResponseSchema = z
  .object({
    artifact_id: z.string(),
    patient_id: z.string(),
    artifact_kind: z.string(),
    state: z.string(),
    summary: z.string(),
    created_at: z.string(),
    model_name: z.string().nullable().optional(),
    evidence_hash: z.string().nullable().optional(),
    original_summary: z.string().nullable().optional(),
    reviewed_by_user_id: z.string().nullable().optional(),
    reviewed_at: z.string().nullable().optional(),
  })
  .strict();

export type AIArtifactResponse = z.infer<typeof aiArtifactResponseSchema>;

export const aiArtifactListResponseSchema = z
  .object({
    artifact_count: z.number().int(),
    items: z.array(aiArtifactResponseSchema),
  })
  .strict();

export type AIArtifactListResponse = z.infer<typeof aiArtifactListResponseSchema>;

// ─── Sarvam AI Conversational & Indic Nutrition Schemas ──────────────────────

export const chatAiRequestSchema = z.object({
  message: z.string(),
  patient_name: z.string().optional(),
});
export type ChatAiRequest = z.infer<typeof chatAiRequestSchema>;

export const chatAiResponseSchema = z.object({
  reply: z.string(),
  safety_checked: z.boolean().optional(),
  provider: z.string().optional(),
});
export type ChatAiResponse = z.infer<typeof chatAiResponseSchema>;

export const analyzeMealAiRequestSchema = z.object({
  description: z.string(),
  patient_name: z.string().optional(),
});
export type AnalyzeMealAiRequest = z.infer<typeof analyzeMealAiRequestSchema>;

export const analyzeMealAiResponseSchema = z.object({
  raw_description: z.string().optional(),
  items: z
    .array(
      z.object({
        name: z.string(),
        portion_text: z.string().optional(),
        calories_kcal: z.number(),
        carbs_g: z.number(),
        protein_g: z.number(),
        fat_g: z.number().optional(),
        fiber_g: z.number().optional(),
        glycemic_index_category: z.string().optional(),
      })
    )
    .optional(),
  total_calories_kcal: z.number(),
  total_carbs_g: z.number(),
  total_protein_g: z.number(),
  total_fat_g: z.number().optional(),
  total_fiber_g: z.number().optional(),
  glycemic_impact: z.string(),
  balanced_plate_score: z.string(),
  patient_guidance_hinglish: z.string(),
  clinician_notes: z.string().optional(),
  source: z.string().optional(),
});
export type AnalyzeMealAiResponse = z.infer<typeof analyzeMealAiResponseSchema>;

export const analyzeMealPhotoAiRequestSchema = z.object({
  image_base64: z.string(),
  mime_type: z.string().optional(),
  patient_name: z.string().optional(),
});
export type AnalyzeMealPhotoAiRequest = z.infer<typeof analyzeMealPhotoAiRequestSchema>;

export const analyzeMealPhotoAiResponseSchema = z.object({
  description: z.string(),
  items: z
    .array(
      z.object({
        name: z.string(),
        portion_text: z.string().optional(),
        calories_kcal: z.number(),
        carbs_g: z.number(),
        protein_g: z.number(),
        fat_g: z.number().optional(),
        fiber_g: z.number().optional(),
        glycemic_index_category: z.string().optional(),
      })
    )
    .optional(),
  total_calories_kcal: z.number(),
  total_carbs_g: z.number(),
  total_protein_g: z.number(),
  total_fat_g: z.number().optional(),
  total_fiber_g: z.number().optional(),
  glycemic_impact: z.string().optional(),
  balanced_plate_score: z.string().optional(),
  patient_guidance_hinglish: z.string().optional(),
  photo_captured: z.boolean().optional(),
  provider: z.string().optional(),
});
export type AnalyzeMealPhotoAiResponse = z.infer<typeof analyzeMealPhotoAiResponseSchema>;

export const transcribeAiRequestSchema = z.object({
  audio_base64: z.string(),
  mime_type: z.string().optional(),
  language_code: z.string().optional(),
  filename: z.string().optional(),
});
export type TranscribeAiRequest = z.infer<typeof transcribeAiRequestSchema>;

export const transcribeAiResponseSchema = z.object({
  transcript: z.string(),
  language_code: z.string().optional(),
  provider: z.string().optional(),
  latency_ms: z.number().optional(),
});
export type TranscribeAiResponse = z.infer<typeof transcribeAiResponseSchema>;