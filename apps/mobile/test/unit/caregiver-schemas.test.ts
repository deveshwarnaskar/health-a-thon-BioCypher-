import { describe, expect, it } from "vitest";
import {
  caregiverCapabilitySchema,
  caregiverPatientListSchema,
  caregiverPatientListItemSchema,
  canReadCaregiverGlucose,
  canRecordCaregiverGlucose,
  GLUCOSE_READ_CAPABILITIES,
  GLUCOSE_WRITE_CAPABILITY,
} from "../../src/services/schemas/caregiver";
import { caregiverKeys } from "../../src/features/caregiver/useCaregiverPatients";

const validItem = {
  relationship_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  patient_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  relationship_label: "test-caregiver",
  status: "verified",
  capabilities: ["read_glucose", "read_meal"],
  expires_at: null,
  name: "Aarav Sharma",
};

describe("Gate 10E-M: Caregiver Patient Discovery Schemas", () => {
  // Scenario 1: Fully valid list item parses
  it("accepts a valid verified relationship item", () => {
    const parsed = caregiverPatientListItemSchema.safeParse(validItem);
    expect(parsed.success).toBe(true);
    if (parsed.success) {
      expect(parsed.data.status).toBe("verified");
      expect(parsed.data.capabilities).toEqual(["read_glucose", "read_meal"]);
      expect(parsed.data.expires_at).toBeNull();
    }
  });

  // Scenario 2: Only verified relationships are ever returned
  it("rejects non-verified relationship statuses", () => {
    const pending = caregiverPatientListItemSchema.safeParse({ ...validItem, status: "pending" });
    expect(pending.success).toBe(false);
  });

  // Scenario 3: Strict DTO — unknown fields are forbidden
  it("rejects unknown keys in the item DTO (strict, extra=forbid)", () => {
    const contaminated = caregiverPatientListItemSchema.safeParse({
      ...validItem,
      risk_score: 0.82,
      glycemic_index: "55",
    });
    expect(contaminated.success).toBe(false);
    if (!contaminated.success) {
      expect(contaminated.error.issues[0]?.message).toContain("Unrecognized key");
    }
  });

  // Scenario 4: Capabilities are verbatim backend tokens; unknown tokens rejected
  it("rejects unknown/imagined capability tokens", () => {
    expect(caregiverCapabilitySchema.safeParse("read_glucose").success).toBe(true);
    expect(caregiverCapabilitySchema.safeParse("super-admin").success).toBe(false);
    const list = caregiverPatientListSchema.safeParse({
      patient_count: 1,
      items: [{ ...validItem, capabilities: ["read_glucose", "steal_all_data"] }],
    });
    expect(list.success).toBe(false);
  });

  // Scenario 5: patient_count must be an integer
  it("rejects fractional patient_count", () => {
    const parsed = caregiverPatientListSchema.safeParse({
      patient_count: 1.5,
      items: [validItem],
    });
    expect(parsed.success).toBe(false);
  });

  // Scenario 6: expires_at may be a timestamp string or null
  it("accepts an expires_at timestamp in addition to null", () => {
    const withExpiry = caregiverPatientListItemSchema.safeParse({
      ...validItem,
      expires_at: "2026-12-31T23:59:59Z",
    });
    expect(withExpiry.success).toBe(true);
  });

  // Scenario 7: List response parses and exposes count + items
  it("parses the full list response envelope", () => {
    const parsed = caregiverPatientListSchema.safeParse({
      patient_count: 1,
      items: [validItem],
    });
    expect(parsed.success).toBe(true);
    if (parsed.success) {
      expect(parsed.data.patient_count).toBe(1);
      expect(parsed.data.items).toHaveLength(1);
      const item = parsed.data.items[0];
      expect(item?.name).toBe("Aarav Sharma");
    }
  });

  // Scenario 8: Capability gate — read requires the exact pair
  it("gates glucose read on the read_glucose + read_meal pair", () => {
    expect(GLUCOSE_READ_CAPABILITIES).toEqual(["read_glucose", "read_meal"]);
    expect(canReadCaregiverGlucose(["read_glucose", "read_meal"])).toBe(true);
    expect(canReadCaregiverGlucose(["read_glucose"])).toBe(false);
    expect(canReadCaregiverGlucose(["read_meal"])).toBe(false);
    expect(canReadCaregiverGlucose([])).toBe(false);
  });

  // Scenario 9: Capability gate — write requires create_glucose only
  it("gates glucose write on create_glucose only", () => {
    expect(GLUCOSE_WRITE_CAPABILITY).toBe("create_glucose");
    expect(canRecordCaregiverGlucose(["read_glucose", "read_meal", "create_glucose"])).toBe(true);
    expect(canRecordCaregiverGlucose(["read_glucose", "read_meal"])).toBe(false);
    expect(canRecordCaregiverGlucose([])).toBe(false);
  });

  // Scenario 10: Query key stability (ephemeral, scoped to the caregiver)
  it("provides deterministic caregiver-scoped query keys", () => {
    expect(caregiverKeys.all).toEqual(["caregivers"]);
    expect(caregiverKeys.me()).toEqual(["caregivers", "me"]);
    expect(caregiverKeys.patients()).toEqual(["caregivers", "me", "patients"]);
    expect(caregiverKeys.patients()).toEqual(caregiverKeys.patients());
  });
});