import { describe, expect, it } from "vitest";
import {
  generateAiArtifactRequestSchema,
  generateAiArtifactResponseSchema,
  reviewAiArtifactRequestSchema,
  reviewAiArtifactResponseSchema,
  aiArtifactResponseSchema,
  aiArtifactListResponseSchema,
} from "../../src/services/schemas/ai";
import { aiEndpoints } from "../../src/services/api/endpoints/ai";

describe("Gate 10M AI Generation & Review Schemas", () => {
  const validUUID = "3fa85f64-5717-4562-b3fc-2c963f66afa6";

  describe("Generate AI Artifact Request Schema", () => {
    it("parses valid generate request with defaults", () => {
      const parsed = generateAiArtifactRequestSchema.parse({
        patient_id: validUUID,
      });
      expect(parsed.patient_id).toBe(validUUID);
    });

    it("parses valid generate request with context and task_type", () => {
      const parsed = generateAiArtifactRequestSchema.parse({
        patient_id: validUUID,
        context: "patient mentions feeling tired",
        task_type: "clinical_summary",
      });
      expect(parsed.context).toBe("patient mentions feeling tired");
      expect(parsed.task_type).toBe("clinical_summary");
    });

    it("rejects forbidden analytical fields (carbs_grams, glycemic_index)", () => {
      expect(() =>
        generateAiArtifactRequestSchema.parse({
          patient_id: validUUID,
          carbs_grams: 50,
        })
      ).toThrow();
      expect(() =>
        generateAiArtifactRequestSchema.parse({
          patient_id: validUUID,
          glycemic_index: "high",
        })
      ).toThrow();
    });
  });

  describe("Generate AI Artifact Response Schema", () => {
    it("parses valid generate response", () => {
      const data = {
        artifact_id: validUUID,
        patient_id: validUUID,
        state: "pending_review",
        summary: "Clinical summary draft",
        model_name: "demo-v1",
        evidence_hash: "abcd1234ef",
      };
      const parsed = generateAiArtifactResponseSchema.parse(data);
      expect(parsed.artifact_id).toBe(validUUID);
      expect(parsed.state).toBe("pending_review");
    });

    it("rejects unexpected fields (strict schema)", () => {
      expect(() =>
        generateAiArtifactResponseSchema.parse({
          artifact_id: validUUID,
          patient_id: validUUID,
          state: "pending_review",
          summary: "Summary",
          autonomous_action: true,
        })
      ).toThrow();
    });
  });

  describe("Review AI Artifact Request & Response Schemas", () => {
    it("validates approve, edit, reject decisions", () => {
      expect(reviewAiArtifactRequestSchema.parse({ decision: "approve" })).toEqual({
        decision: "approve",
      });
      expect(
        reviewAiArtifactRequestSchema.parse({
          decision: "edit",
          edited_summary: "Clinician edited summary",
        })
      ).toEqual({
        decision: "edit",
        edited_summary: "Clinician edited summary",
      });
      expect(reviewAiArtifactRequestSchema.parse({ decision: "reject" })).toEqual({
        decision: "reject",
      });
    });

    it("rejects illegal decisions", () => {
      expect(() =>
        reviewAiArtifactRequestSchema.parse({ decision: "self_approve" })
      ).toThrow();
      expect(() =>
        reviewAiArtifactRequestSchema.parse({ decision: "titrate" })
      ).toThrow();
    });
  });

  describe("AI Endpoints Definition", () => {
    it("has generate, queue, detail, and review endpoints", () => {
      expect(aiEndpoints.generate.method).toBe("POST");
      expect(aiEndpoints.generate.path).toBe("/api/v2/clinical/ai-artifacts/generate");
      expect(aiEndpoints.generate.requiresIdempotencyKey).toBe(true);
      expect(aiEndpoints.review.method).toBe("POST");
      expect(aiEndpoints.review.requiresIdempotencyKey).toBe(true);
      expect(aiEndpoints.queue.method).toBe("GET");
      expect(aiEndpoints.queue.requiresIdempotencyKey).toBe(false);
    });

    it("parses review response, artifact response, and list response", () => {
      const revResp = reviewAiArtifactResponseSchema.parse({
        artifact_id: validUUID,
        state: "approved",
        reviewed_by_user_id: validUUID,
      });
      expect(revResp.state).toBe("approved");

      const artResp = aiArtifactResponseSchema.parse({
        artifact_id: validUUID,
        patient_id: validUUID,
        artifact_kind: "clinical_summary",
        state: "pending_review",
        summary: "Patient glucose stable",
        created_at: "2026-09-17T12:00:00Z",
        model_name: "deterministic-demo-v1",
        evidence_hash: "hash123",
      });
      expect(artResp.model_name).toBe("deterministic-demo-v1");

      const listResp = aiArtifactListResponseSchema.parse({
        artifact_count: 1,
        items: [artResp],
      });
      expect(listResp.artifact_count).toBe(1);
    });
  });
});
