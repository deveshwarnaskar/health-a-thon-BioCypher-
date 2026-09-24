import { describe, expect, it } from "vitest";
import {
  generateAiArtifactRequestSchema,
  generateAiArtifactResponseSchema,
  reviewAiArtifactRequestSchema,
  reviewAiArtifactResponseSchema,
  aiArtifactResponseSchema,
  aiArtifactListResponseSchema,
  analyzeMealPhotoAiRequestSchema,
  analyzeMealPhotoAiResponseSchema,
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

  describe("Meal Photo AI Analysis Schemas", () => {
    it("validates valid analyze-meal-photo request", () => {
      const parsed = analyzeMealPhotoAiRequestSchema.parse({
        image_base64: "dGVzdC1iYXNlNjQ=",
        mime_type: "image/jpeg",
        patient_name: "Aarav Sharma",
      });
      expect(parsed.image_base64).toBe("dGVzdC1iYXNlNjQ=");
      expect(parsed.mime_type).toBe("image/jpeg");
    });

    it("validates valid analyze-meal-photo response", () => {
      const parsed = analyzeMealPhotoAiResponseSchema.parse({
        description: "2 roti with dal and mixed sabzi",
        items: [
          {
            name: "Roti",
            portion_text: "2 medium",
            calories_kcal: 240,
            carbs_g: 40,
            protein_g: 6,
          },
          {
            name: "Dal",
            portion_text: "1 katori",
            calories_kcal: 150,
            carbs_g: 22,
            protein_g: 9,
          },
        ],
        total_calories_kcal: 390,
        total_carbs_g: 62,
        total_protein_g: 15,
        glycemic_impact: "MODERATE",
        patient_guidance_hinglish: "Yeh thali achhi hai, salad zaroor add karein.",
        provider: "gemini_flash_lite_vision",
      });
      expect(parsed.items?.length).toBe(2);
      expect(parsed.total_calories_kcal).toBe(390);
      expect(parsed.provider).toBe("gemini_flash_lite_vision");
    });

    it("verifies analyzeMealPhoto endpoint definition", () => {
      expect(aiEndpoints.analyzeMealPhoto.method).toBe("POST");
      expect(aiEndpoints.analyzeMealPhoto.path).toBe("/api/v2/ai/analyze-meal-photo");
      expect(aiEndpoints.analyzeMealPhoto.requiresIdempotencyKey).toBe(false);
    });
  });
});
