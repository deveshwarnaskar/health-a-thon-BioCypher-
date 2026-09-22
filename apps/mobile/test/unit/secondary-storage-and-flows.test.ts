import { describe, expect, it, beforeEach } from "vitest";
import {
  saveSecondaryEvent,
  getSecondaryEvents,
  clearSecondaryStorageForTesting,
} from "../../src/features/patient/secondaryStorage";

describe("Secondary Storage & Flow Events", () => {
  beforeEach(() => {
    clearSecondaryStorageForTesting();
  });

  it("stores and retrieves activity events with correct patient scoping", async () => {
    await saveSecondaryEvent({
      patientId: "patient-123",
      type: "activity",
      title: "Walking (30 mins)",
      subtitle: "Moderate intensity • 15:30",
      timestamp: "2026-09-22T15:30:00Z",
      details: {
        type: "walking",
        durationMinutes: 30,
        intensity: "moderate",
        date: "2026-09-22",
        time: "15:30",
        notes: "Evening walk in park",
      },
    });

    const patient1Events = await getSecondaryEvents("patient-123");
    expect(patient1Events.length).toBe(1);
    expect(patient1Events[0]?.title).toBe("Walking (30 mins)");
    expect(patient1Events[0]?.type).toBe("activity");
    expect(patient1Events[0]?.details?.durationMinutes).toBe(30);

    // Other patient shouldn't see it
    const patient2Events = await getSecondaryEvents("patient-999");
    expect(patient2Events.length).toBe(0);
  });

  it("stores weight and blood pressure vital observations", async () => {
    await saveSecondaryEvent({
      patientId: "patient-123",
      type: "vital",
      title: "Weight: 72.5 kg",
      subtitle: "Morning fasting • 07:15",
      timestamp: "2026-09-22T07:15:00Z",
      details: {
        weight: 72.5,
        unit: "kg",
        context: "morning_fasting",
      },
    });

    await saveSecondaryEvent({
      patientId: "patient-123",
      type: "vital",
      title: "Blood Pressure: 120/80 mmHg",
      subtitle: "Pulse 72 BPM • Sitting",
      timestamp: "2026-09-22T08:00:00Z",
      details: {
        systolic: 120,
        diastolic: 80,
        pulse: 72,
        position: "sitting",
      },
    });

    const vitals = await getSecondaryEvents("patient-123", "vital");
    expect(vitals.length).toBe(2);
    expect(vitals.some((v) => v.title.includes("Weight"))).toBe(true);
    expect(vitals.some((v) => v.title.includes("120/80"))).toBe(true);
  });

  it("stores non-diagnostic symptom observations and sleep logs", async () => {
    await saveSecondaryEvent({
      patientId: "patient-123",
      type: "symptom",
      title: "Observed Symptoms: Shaky, Sweating",
      subtitle: "Felt shaky before lunch • Glucose: 68 mg/dL",
      timestamp: "2026-09-22T11:45:00Z",
      details: {
        selectedSymptoms: ["shaky", "sweating"],
        nearbyGlucose: 68,
        notes: "Drank orange juice",
      },
    });

    await saveSecondaryEvent({
      patientId: "patient-123",
      type: "sleep",
      title: "Sleep: 7h 30m",
      subtitle: "Quality: Restful",
      timestamp: "2026-09-22T06:30:00Z",
      details: {
        hours: 7,
        minutes: 30,
        quality: "restful",
      },
    });

    const symptoms = await getSecondaryEvents("patient-123", "symptom");
    expect(symptoms.length).toBe(1);
    expect(symptoms[0]?.details?.selectedSymptoms).toContain("shaky");

    const sleep = await getSecondaryEvents("patient-123", "sleep");
    expect(sleep.length).toBe(1);
    expect(sleep[0]?.details?.hours).toBe(7);
  });
});
