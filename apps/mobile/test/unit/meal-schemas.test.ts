import { describe, expect, it } from "vitest";
import {
  KATORI_PORTION_LABELS,
  KATORI_SIZE_NAMES,
  KATORI_VOLUMES,
  confirmMealRequestSchema,
  confirmMealResponseSchema,
  logMealRequestSchema,
  logMealResponseSchema,
  mealPortionRequestSchema,
} from "../../src/services/schemas/meals";
import {
  clinicianMealObservationSchema,
  patientMealObservationSchema,
  patientObservationFeedSchema,
} from "../../src/services/schemas/clinical";
import { assertPatientSafeFeed } from "../../src/features/glucose/feedSafety";
import { can, capabilitiesForRole } from "../../src/authz/capabilities";

describe("Gate 10H-M Meal Schemas & DTO Safety", () => {
  const validUUID = "3fa85f64-5717-4562-b3fc-2c963f66afa6";

  describe("Katori volumetric portions (10H-M-03, 10H-M-04)", () => {
    it("defines canonical Indian household katori volumes: 150, 220, 350 ml", () => {
      expect(KATORI_VOLUMES).toEqual([150, 220, 350]);
      expect(KATORI_PORTION_LABELS[150]).toBe("Small (150 ml)");
      expect(KATORI_PORTION_LABELS[220]).toBe("Medium (220 ml)");
      expect(KATORI_PORTION_LABELS[350]).toBe("Large (350 ml)");
      expect(KATORI_SIZE_NAMES[150]).toBe("small");
      expect(KATORI_SIZE_NAMES[220]).toBe("medium");
      expect(KATORI_SIZE_NAMES[350]).toBe("large");
    });

    it("parses valid volumetric portion requests", () => {
      for (const vol of KATORI_VOLUMES) {
        const portion = {
          food_key: "dal",
          katori_volume_ml: vol,
          quantity: 1.5,
        };
        expect(mealPortionRequestSchema.parse(portion)).toEqual(portion);
      }
    });

    it("rejects non-canonical katori volumes (10H-M-04)", () => {
      expect(
        mealPortionRequestSchema.safeParse({
          food_key: "dal",
          katori_volume_ml: 130, // invalid volume
          quantity: 1.0,
        }).success
      ).toBe(false);

      expect(
        mealPortionRequestSchema.safeParse({
          food_key: "rice",
          katori_volume_ml: 500, // invalid volume
          quantity: 1.0,
        }).success
      ).toBe(false);
    });

    it("enforces quantity bounds [0.1, 100] (10H-M-04)", () => {
      expect(
        mealPortionRequestSchema.safeParse({
          food_key: "dal",
          katori_volume_ml: 220,
          quantity: 0.1,
        }).success
      ).toBe(true);

      expect(
        mealPortionRequestSchema.safeParse({
          food_key: "dal",
          katori_volume_ml: 220,
          quantity: 100,
        }).success
      ).toBe(true);

      // 0 or negative quantity is invalid
      expect(
        mealPortionRequestSchema.safeParse({
          food_key: "dal",
          katori_volume_ml: 220,
          quantity: 0,
        }).success
      ).toBe(false);

      // > 100 quantity is invalid
      expect(
        mealPortionRequestSchema.safeParse({
          food_key: "dal",
          katori_volume_ml: 220,
          quantity: 101,
        }).success
      ).toBe(false);
    });

    it("strictly rejects extraneous fields on portion request", () => {
      expect(
        mealPortionRequestSchema.safeParse({
          food_key: "dal",
          katori_volume_ml: 220,
          quantity: 1.0,
          carbs: 45, // forbidden
        }).success
      ).toBe(false);
    });
  });

  describe("LogMealRequest and Response schemas", () => {
    it("parses valid log meal request with portion", () => {
      const payload = {
        patient_id: validUUID,
        description: "Dal and rice",
        portion: {
          food_key: "rice",
          katori_volume_ml: 220 as const,
          quantity: 1.0,
        },
        recorded_at: "2026-09-17T12:00:00Z",
      };
      expect(logMealRequestSchema.parse(payload)).toEqual(payload);
    });

    it("parses valid log meal request without portion", () => {
      const payload = {
        patient_id: validUUID,
        description: "Fresh apple",
      };
      expect(logMealRequestSchema.parse(payload)).toEqual({
        patient_id: validUUID,
        description: "Fresh apple",
      });
    });

    it("rejects empty description or invalid UUID (10H-M-04)", () => {
      expect(
        logMealRequestSchema.safeParse({
          patient_id: validUUID,
          description: "", // empty
        }).success
      ).toBe(false);

      expect(
        logMealRequestSchema.safeParse({
          patient_id: "not-a-uuid",
          description: "Meal",
        }).success
      ).toBe(false);
    });

    it("parses valid log meal response", () => {
      const response = {
        meal_observation_id: "obs-meal-01",
        patient_id: validUUID,
        portion_label: "medium",
        quantity: 1.0,
      };
      expect(logMealResponseSchema.parse(response)).toEqual(response);
    });
  });

  describe("ConfirmMealRequest and Response schemas", () => {
    it("parses empty confirm request body (defaults)", () => {
      expect(confirmMealRequestSchema.parse({})).toEqual({});
    });

    it("parses confirm request with corrections", () => {
      const payload = {
        corrected_description: "Corrected 1.5 katori dal",
        corrected_portion: {
          food_key: "dal",
          katori_volume_ml: 220 as const,
          quantity: 1.5,
        },
      };
      expect(confirmMealRequestSchema.parse(payload)).toEqual(payload);
    });

    it("parses valid confirm meal response (10H-M-08)", () => {
      const response = {
        meal_observation_id: "obs-meal-01",
        patient_id: validUUID,
        confirmation: "confirmed",
      };
      expect(confirmMealResponseSchema.parse(response)).toEqual(response);
    });
  });

  describe("DTO Safety & Information Asymmetry (10H-M-16, 10H-M-17, 10H-M-18, 10H-M-19)", () => {
    it("patientMealObservationSchema excludes carbs_grams and glycemic_index (10H-M-16, 10H-M-17)", () => {
      const safeMeal = {
        kind: "meal" as const,
        description: "Moong dal khichdi",
        portion_label: "medium",
        quantity: 1.0,
        recorded_at: "2026-09-17T12:00:00Z",
        confirmed: true,
      };
      expect(patientMealObservationSchema.parse(safeMeal)).toEqual(safeMeal);

      // Rejects carbs_grams
      expect(
        patientMealObservationSchema.safeParse({
          ...safeMeal,
          carbs_grams: 48,
        }).success
      ).toBe(false);

      // Rejects glycemic_index
      expect(
        patientMealObservationSchema.safeParse({
          ...safeMeal,
          glycemic_index: "low",
        }).success
      ).toBe(false);
    });

    it("assertPatientSafeFeed refuses feed containing forbidden nutrition metrics", () => {
      const safeFeed = {
        patient_id: validUUID,
        items: [
          {
            kind: "meal" as const,
            description: "Roti with sabzi",
            portion_label: "small",
            quantity: 2.0,
            recorded_at: "2026-09-17T13:00:00Z",
            confirmed: false,
          },
        ],
      };
      expect(assertPatientSafeFeed(safeFeed)).toEqual(safeFeed);

      const unsafeFeed = {
        patient_id: validUUID,
        items: [
          {
            kind: "meal" as const,
            description: "Roti with sabzi",
            portion_label: "small",
            quantity: 2.0,
            carbs_grams: 45,
            recorded_at: "2026-09-17T13:00:00Z",
            confirmed: false,
          } as unknown as typeof safeFeed.items[0],
        ],
      };
      expect(() => assertPatientSafeFeed(unsafeFeed)).toThrow(
        "Patient-facing feed contained clinician-only fields."
      );
    });

    it("clinician meal observation schema accepts permitted clinician analytics (10H-M-19)", () => {
      const clinicianMeal = {
        kind: "meal" as const,
        observation_id: "obs-meal-01",
        description: "Rice and sambar",
        portion_label: "large",
        quantity: 1.0,
        carbs_grams: 62.5,
        glycemic_index: "high",
        recorded_at: "2026-09-17T14:00:00Z",
        confirmation: "confirmed",
      };
      expect(clinicianMealObservationSchema.parse(clinicianMeal)).toEqual(clinicianMeal);
    });

    it("caregiver role cannot confirm meals (Domain Gate 03 / Gate 10H-B invariant)", () => {
      const caregiverCaps = capabilitiesForRole("Caregiver");
      expect(caregiverCaps).toContain("CREATE_MEAL");
      expect(caregiverCaps).toContain("READ_MEAL");
      // Caregiver does NOT have confirmation authority
      expect(caregiverCaps).not.toContain("CONFIRM_MEAL_OBSERVATION");
    });

    it("dietitian role holds appropriate clinician capabilities (10H-M-20)", () => {
      const dietitianCaps = capabilitiesForRole("Dietitian");
      expect(dietitianCaps).toContain("READ_OBSERVATIONS");
      expect(dietitianCaps).toContain("WRITE_OBSERVATIONS");
      expect(dietitianCaps).toContain("READ_PATIENT");
      expect(can("Dietitian", "READ_OBSERVATIONS")).toBe(true);
      expect(can("Dietitian", "READ_PATIENT")).toBe(true);
    });
  });
});
