import { describe, expect, it } from "vitest";
import {
  calculateGlycemicMetrics,
  calculatePersonalBaseline,
  calculateTemporalAlignment,
  calculateDataCoverage,
  DETERMINISTIC_INTELLIGENCE_VERSION,
} from "../../src/services/clinical/deterministicIntelligence";

describe("Deterministic Clinical Intelligence Layer", () => {
  it("computes accurate glycemic metrics adhering to ADA/EASD targets", () => {
    const readings = [
      { value_mg_dl: 65, taken_at: "2026-09-15T08:00:00Z", tag: "fasting" }, // TBR (<70)
      { value_mg_dl: 110, taken_at: "2026-09-15T12:00:00Z", tag: "before_meal" }, // TIR (70-180)
      { value_mg_dl: 140, taken_at: "2026-09-15T14:00:00Z", tag: "after_meal" }, // TIR (70-180)
      { value_mg_dl: 210, taken_at: "2026-09-15T20:00:00Z", tag: "bedtime" }, // TAR (>180)
    ];

    const result = calculateGlycemicMetrics(readings, 14);

    expect(result.version).toBe(DETERMINISTIC_INTELLIGENCE_VERSION);
    expect(result.totalObservations).toBe(4);
    // Mean = (65 + 110 + 140 + 210) / 4 = 131.25 -> 131.3
    expect(result.meanMgDl).toBe(131.3);
    // Median of [65, 110, 140, 210] = (110 + 140) / 2 = 125
    expect(result.medianMgDl).toBe(125);
    // TIR: 2 out of 4 = 50%
    expect(result.timeInRangePct).toBe(50);
    // TBR: 1 out of 4 = 25%
    expect(result.timeBelowRangePct).toBe(25);
    // TAR: 1 out of 4 = 25%
    expect(result.timeAboveRangePct).toBe(25);
    // GMI: 3.31 + 0.02392 * 131.25 = 6.45 -> 6.4%
    expect(result.gmiPct).toBe(6.4);
    // estimatedA1cPct: (131.25 + 46.7) / 28.7 = 6.2%
    expect(result.estimatedA1cPct).toBe(6.2);
    expect(result.readingCountByTag).toEqual({
      fasting: 1,
      before_meal: 1,
      after_meal: 1,
      bedtime: 1,
    });
  });

  it("handles empty observation lists gracefully without throwing", () => {
    const result = calculateGlycemicMetrics([], 14);
    expect(result.totalObservations).toBe(0);
    expect(result.meanMgDl).toBeNull();
    expect(result.timeInRangePct).toBeNull();
  });

  it("computes personal rolling baseline using robust median and MAD", () => {
    const observations = [
      { value_mg_dl: 100, taken_at: "2026-09-10T08:00:00Z" },
      { value_mg_dl: 105, taken_at: "2026-09-11T08:00:00Z" },
      { value_mg_dl: 110, taken_at: "2026-09-12T08:00:00Z" },
      { value_mg_dl: 115, taken_at: "2026-09-13T08:00:00Z" },
      { value_mg_dl: 120, taken_at: "2026-09-14T08:00:00Z" },
    ];

    const baseline = calculatePersonalBaseline(observations, 14);
    expect(baseline.medianMgDl).toBe(110);
    expect(baseline.madMgDl).toBe(5);
    expect(baseline.baselineRange).toEqual({ low: 103, high: 118 });
    expect(baseline.descriptiveNote).toContain("Personal 14-day median baseline is 110 mg/dL");
  });

  it("aligns meals and glucose temporally with non-causal language", () => {
    const meals = [
      {
        id: "meal-1",
        description: "Roti with Dal",
        recorded_at: "2026-09-18T12:30:00Z",
        portion_label: "1.5 katori",
      },
    ];

    const readings = [
      {
        id: "g-1",
        value_mg_dl: 145,
        taken_at: "2026-09-18T13:30:00Z", // +60 min
        tag: "after_meal",
      },
    ];

    const alignments = calculateTemporalAlignment(meals, readings);
    expect(alignments.length).toBe(1);
    expect(alignments[0]?.deltaMinutes).toBe(60);
    expect(alignments[0]?.windowLabel).toBe("1h Post-meal (+60m)");
    expect(alignments[0]?.relationshipNote).toContain("Observed reading of 145 mg/dL");
    expect(alignments[0]?.relationshipNote).not.toContain("caused");
  });

  it("evaluates data coverage without calculating a clinical risk score", () => {
    const meals = [
      { description: "Breakfast", recorded_at: new Date().toISOString() },
    ];
    const readings = [
      { value_mg_dl: 120, taken_at: new Date().toISOString() },
    ];

    const coverage = calculateDataCoverage(readings, meals, 14);
    expect(coverage.evaluationWindowDays).toBe(14);
    expect(coverage.activeLoggedDays).toBe(1);
    expect(coverage.coverageText).toBe("1 of requested 14 days logged");
    expect((coverage as any).risk_score).toBeUndefined();
    expect((coverage as any).severity).toBeUndefined();
  });
});
