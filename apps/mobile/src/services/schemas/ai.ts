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