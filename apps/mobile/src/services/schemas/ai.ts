import { z } from "zod";

// ─── AI artifact review (verified contract) ──────────────────────────────
// Mirrors models.py:ReviewAIArtifactRequest/Response.

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
  })
  .strict();

export type AIArtifactResponse = z.infer<typeof aiArtifactResponseSchema>;