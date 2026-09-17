import { describe, expect, it } from "vitest";
import {
  clinicianGlucoseObservationSchema,
  clinicianMealObservationSchema,
  clinicianObservationFeedSchema,
  patientGlucoseObservationSchema,
  patientMealObservationSchema,
  patientObservationFeedSchema,
  type ClinicianObservationFeedResponse,
} from "../../src/services/schemas/clinical";
import {
  assertClinicianSafeFeed,
  isClinicianObservation,
} from "../../src/features/doctor/api";

/**
 * Gate 10F-M clinician-schema contract mirror tests.
 *
 * Verifies the sealed clinician feed DTOs while proving the patient-facing
 * schemas were NOT widened (Gate 10A §13 information-asymmetry invariant):
 * carbs_grams / glycemic_index / observation lifecycle facts are rejected by
 * every patient/caregiver surface schema.
 */
describe("clinician observation schemas (Gate 10F-B → Gate 10F-M)", () => {
  const glucoseItem = {
    kind: "glucose",
    observation_id: "obs-1",
    value_mg_dl: 118,
    tag: "fasting",
    taken_at: "2026-09-17T08:00:00Z",
    confirmation: "confirmed",
  };

  const mealItem = {
    kind: "meal",
    observation_id: "obs-2",
    description: "Rice and dal",
    portion_label: "plate",
    quantity: 1,
    carbs_grams: 55,
    glycemic_index: "medium",
    recorded_at: "2026-09-17T09:00:00Z",
    confirmation: "confirmed",
  };

  it("parses a sealed clinician glucose observation", () => {
    expect(clinicianGlucoseObservationSchema.parse(glucoseItem)).toEqual(glucoseItem);
  });

  it("parses a sealed clinician meal observation with carbs_grams + glycemic_index", () => {
    expect(clinicianMealObservationSchema.parse(mealItem)).toEqual(mealItem);
  });

  it("parses a mixed clinician observation feed", () => {
    const feed = { patient_id: "p-1", items: [glucoseItem, mealItem] };
    expect(clinicianObservationFeedSchema.parse(feed)).toEqual(feed);
  });

  it("REJECTS unknown keys (strict) on the clinician feed", () => {
    expect(clinicianGlucoseObservationSchema.safeParse({ ...glucoseItem, leaked: 1 }).success).toBe(false);
    expect(clinicianMealObservationSchema.safeParse({ ...mealItem, extra: "x" }).success).toBe(false);
    expect(clinicianObservationFeedSchema.safeParse({ patient_id: "p-1", extra: 1 }).success).toBe(false);
  });

  it("REJECTS clinician lifecycle facts on the patient glucose schema (asymmetry preserved)", () => {
    // A patient/meal item must never render observation_id/confirmation;
    // the patient-facing schema stays untouched and strict.
    const patientGlucose = {
      kind: "glucose",
      observation_id: "obs-1",
      value_mg_dl: 118,
      taken_at: "2026-09-17T08:00:00Z",
      confirmed: true,
    };
    expect(patientGlucoseObservationSchema.safeParse(patientGlucose).success).toBe(false);

    const patientGlucoseWithCarbs = {
      kind: "glucose",
      value_mg_dl: 118,
      taken_at: "2026-09-17T08:00:00Z",
      confirmed: true,
      carbs_grams: 55,
    };
    expect(patientGlucoseObservationSchema.safeParse(patientGlucoseWithCarbs).success).toBe(false);
  });

  it("REJECTS carbs_grams / glycemic_index on the patient meal schema (asymmetry preserved)", () => {
    const patientMealWithCarbs = {
      kind: "meal",
      description: "Rice and dal",
      portion_label: "plate",
      quantity: 1,
      carbs_grams: 55,
      glycemic_index: "medium",
      recorded_at: "2026-09-17T09:00:00Z",
      confirmed: true,
    };
    expect(patientMealObservationSchema.safeParse(patientMealWithCarbs).success).toBe(false);
    expect(patientObservationFeedSchema.safeParse({ patient_id: "p-1", items: [patientMealWithCarbs] }).success).toBe(false);
  });

  it("REJECTS a clinician-shaped item on the patient feed", () => {
    const patientFeed = { patient_id: "p-1", items: [mealItem] };
    expect(patientObservationFeedSchema.safeParse(patientFeed).success).toBe(false);
  });
});

describe("clinician feed defense-in-depth guard (Gate 10A §13, Doctor direction)", () => {
  it("recognizes clinician lifecycle markers on feed items", () => {
    expect(
      isClinicianObservation({ kind: "glucose", observation_id: "obs-1", confirmation: "confirmed" })
    ).toBe(true);
  });

  it("refuses patient-DTO items that lack clinician lifecycle markers", () => {
    // Patient-facing items carry `confirmed`, never `confirmation`/observation_id.
    expect(
      isClinicianObservation({ kind: "glucose", value_mg_dl: 118, confirmed: true })
    ).toBe(false);
    expect(isClinicianObservation(null)).toBe(false);
    expect(isClinicianObservation("meal")).toBe(false);
  });

  it("passes a conforming clinician feed through assertClinicianSafeFeed", () => {
    const feed: ClinicianObservationFeedResponse = {
      patient_id: "p-1",
      items: [
        {
          kind: "glucose",
          observation_id: "obs-1",
          value_mg_dl: 118,
          tag: "fasting",
          taken_at: "2026-09-17T08:00:00Z",
          confirmation: "confirmed",
        },
      ],
    };
    expect(assertClinicianSafeFeed(feed)).toEqual(feed);
  });

  it("rejects a feed whose item is patient-shaped", () => {
    const badFeed = {
      patient_id: "p-1",
      items: [{ kind: "glucose", value_mg_dl: 118, taken_at: "2026-09-17T08:00:00Z", confirmed: true }],
    };
    expect(() => assertClinicianSafeFeed(badFeed as unknown as ClinicianObservationFeedResponse)).toThrow();
  });
});