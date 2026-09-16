import { describe, expect, it } from "vitest";
import {
  authVerifyResponseSchema,
  ingestGlucoseRequestSchema,
  ingestGlucoseResponseSchema,
  patientObservationFeedSchema,
  PATIENT_FACING_FORBIDDEN_FIELDS,
} from "../../src/services/schemas";
import { reviewAiArtifactRequestSchema } from "../../src/services/schemas/ai";
import { contractStatus } from "../../src/services/schemas/contract-status";

describe("verified backend contract schemas (Gate 10A §12)", () => {
  it("parses an AuthVerifyResponse", () => {
    const result = authVerifyResponseSchema.safeParse({
      actor_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      tenant_id: "c7a85f64-5717-4562-b3fc-2c963f66afa7",
      roles: ["patient"],
      facility_id: "d8a85f64-5717-4562-b3fc-2c963f66afa8",
    });
    expect(result.success).toBe(true);
  });

  it("rejects unknown fields (strict contract, no drift)", () => {
    const result = authVerifyResponseSchema.safeParse({
      actor_id: "a",
      tenant_id: "t",
      roles: ["patient"],
      invented_field: true,
    });
    expect(result.success).toBe(false);
  });

  it("parses the patient observation feed", () => {
    const result = patientObservationFeedSchema.safeParse({
      patient_id: "p-1",
      items: [
        { kind: "glucose", value_mg_dl: 120, tag: "fasting", taken_at: "2026-09-16T10:00:00Z", confirmed: true },
        { kind: "meal", description: "katori", portion_label: "1.0", quantity: 1, recorded_at: "2026-09-16T11:00:00Z", confirmed: false },
      ],
    });
    expect(result.success).toBe(true);
  });

  it("enforces the information-asymmetry invariant on patient-facing feeds", () => {
    const patientFacing = patientObservationFeedSchema.safeParse({
      patient_id: "p-1",
      items: [
        {
          kind: "meal",
          description: "dal",
          carbs_grams: 24,
          glycemic_index: "high",
          recorded_at: "2026-09-16T11:00:00Z",
          confirmed: true,
        },
      ],
    });
    expect(patientFacing.success).toBe(false);
    expect(PATIENT_FACING_FORBIDDEN_FIELDS).toContain("carbs_grams");
    expect(PATIENT_FACING_FORBIDDEN_FIELDS).toContain("glycemic_index");
  });

  it("enforces glucose bounds 20..600 on ingestion requests", () => {
    expect(
      ingestGlucoseRequestSchema.safeParse({
        patient_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        value_mg_dl: 610,
      }).success,
    ).toBe(false);
    expect(
      ingestGlucoseRequestSchema.safeParse({
        patient_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        value_mg_dl: 10,
      }).success,
    ).toBe(false);
    expect(
      ingestGlucoseRequestSchema.safeParse({
        patient_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        value_mg_dl: 120,
        taken_at: "2026-09-16T10:00:00Z",
      }).success,
    ).toBe(true);
  });

  it("shapes the verified ingestion response", () => {
    const result = ingestGlucoseResponseSchema.safeParse({
      observation_id: "obs-1",
      patient_id: "p-1",
      value_mg_dl: 120,
      taken_at: "2026-09-16T10:00:00Z",
    });
    expect(result.success).toBe(true);
  });

  it("only authorizes approve|edit|reject decisions for AI review", () => {
    expect(reviewAiArtifactRequestSchema.safeParse({ decision: "reject" }).success).toBe(true);
    expect(reviewAiArtifactRequestSchema.safeParse({ decision: "delete" }).success).toBe(false);
  });

  it("marks all audited contracts verified (no fabricated endpoints)", () => {
    expect(contractStatus("AuthVerifyResponse")).toBe("verified");
    expect(contractStatus("ReviewAIArtifactRequest/Response")).toBe("verified");
    expect(contractStatus("unmounted endpoint")).toBe("pending");
  });
});