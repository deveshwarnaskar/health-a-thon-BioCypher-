import { describe, expect, it } from "vitest";
import {
  ADA_EASD_TARGETS,
  aggregateCohortMetrics,
  buildDailyMeanSeries,
  classifyCohortStatus,
  compareCohortTrends,
  computeMonitoringDistribution,
  computeStatusDistribution,
  deriveAttentionFlags,
  filterReadingsInWindow,
  groupCareGapTasks,
  summarizeReviewQueue,
  type CohortClientReading,
  type CohortPatientReadings,
} from "../../src/services/clinical/cohortClinicalAnalysis";

const DAY_MS = 24 * 60 * 60 * 1000;
const NOW = Date.UTC(2026, 3, 15, 12, 0, 0); // 2026-04-15T12:00:00Z

function reading(value_mg_dl: number, daysAgo: number, hour = 12): CohortClientReading {
  const t = new Date(NOW - daysAgo * DAY_MS);
  t.setUTCHours(hour, 0, 0, 0);
  return { value_mg_dl, taken_at: t.toISOString(), tag: null };
}

function patient(
  id: string,
  name: string,
  readings: CohortClientReading[]
): CohortPatientReadings {
  return { patientId: id, name, uh_id: `UH-${id}`, readings };
}

describe("cohortClinicalAnalysis", () => {
  describe("filterReadingsInWindow", () => {
    it("keeps only readings inside the trailing window and sorts ascending", () => {
      const readings = [reading(100, 10), reading(120, 3), reading(110, 5), reading(90, 1)];
      const filtered = filterReadingsInWindow(readings, 7, NOW);
      expect(filtered).toHaveLength(3);
      const times = filtered.map((r) => new Date(r.taken_at).getTime());
      expect(times).toEqual([...times].sort((a, b) => a - b));
      expect(filtered.every((r) => r.value_mg_dl !== 100)).toBe(true);
    });

    it("excludes readings after 'now'", () => {
      const future = { value_mg_dl: 100, taken_at: new Date(NOW + 1 * DAY_MS).toISOString(), tag: null };
      const filtered = filterReadingsInWindow([future], 7, NOW);
      expect(filtered).toHaveLength(0);
    });
  });

  describe("aggregateCohortMetrics", () => {
    it("averages per-patient metrics without letting volume skew the cohort", () => {
      const a = patient("A", "Patient A", [
        reading(110, 1),
        reading(120, 2),
        reading(130, 3),
      ]);
      const b = patient("B", "Patient B", [reading(90, 1), reading(100, 2)]);

      const metrics = aggregateCohortMetrics([a, b], 7, NOW);

      expect(metrics.patientCount).toBe(2);
      expect(metrics.sampleSize).toBe(2);
      expect(metrics.readingCount).toBe(5);
      // Patient A mean 120, Patient B mean 95 → cohort mean 107.5
      expect(metrics.meanMgDl).toBe(107.5);
      expect(metrics.tirPct).toBe(100);
      expect(metrics.lastReadingAt).not.toBeNull();
    });

    it("returns sampleSize 0 when no patient has readings in the window", () => {
      const metrics = aggregateCohortMetrics([patient("A", "A", [reading(120, 30)])], 7, NOW);
      expect(metrics.sampleSize).toBe(0);
      expect(metrics.meanMgDl).toBeNull();
      expect(metrics.readingCount).toBe(0);
    });
  });

  describe("buildDailyMeanSeries", () => {
    it("produces one pooled-average point per day, oldest first", () => {
      const a = patient("A", "A", [reading(100, 2, 8), reading(120, 2, 12)]);
      const b = patient("B", "B", [reading(200, 1, 8)]);
      const series = buildDailyMeanSeries([a, b], 7, NOW);
      expect(series.map((p) => p.value)).toEqual([110, 200]);
      expect(series[0]?.dayStart).toBeLessThan(series[1]?.dayStart ?? Infinity);
      expect(typeof series[0]?.label).toBe("string");
    });
  });

  describe("deriveAttentionFlags", () => {
    it("flags severe hypoglycemia, reduced TIR and high variability", () => {
      const p = patient("A", "Patient A", [
        reading(40, 1, 6), // < 54 → severe hypo
        reading(300, 1, 12), // above range depresses TIR
        reading(550, 2, 8), // high excursion → CV spike
        reading(60, 2, 20),
      ]);
      const labels = deriveAttentionFlags(p, 7, NOW).map((f) => f.label);
      expect(labels).toContain("Severe hypoglycemia reading");
      expect(labels).toContain("Reduced time in range");
    });

    it("flags missing data when no readings exist in the window", () => {
      const p = patient("A", "Patient A", [reading(120, 30)]);
      const flags = deriveAttentionFlags(p, 7, NOW);
      expect(flags.some((f) => f.label === "No recent glucose data")).toBe(true);
    });

    it("returns no urgent flags for a well-controlled patient", () => {
      const p = patient("A", "Patient A", [reading(110, 1), reading(120, 2), reading(130, 3)]);
      const severity = deriveAttentionFlags(p, 7, NOW).every((f) => f.severity === "observing");
      expect(severity).toBe(true);
    });
  });

  describe("classifyCohortStatus", () => {
    it("identifies a controlled patient", () => {
      const { bucket } = classifyCohortStatus(
        { tirPct: 80, tbrPct: 2, cvPct: 25, hadSevereHypo: false },
        7,
        NOW
      );
      expect(bucket).toBe("controlled");
    });

    it("downgrades suboptimal TIR to watch", () => {
      const { bucket } = classifyCohortStatus(
        { tirPct: 60, tbrPct: 2, cvPct: 25, hadSevereHypo: false },
        7,
        NOW
      );
      expect(bucket).toBe("watch");
    });

    it("escalates an unsafe TBR to needs_review", () => {
      const { bucket } = classifyCohortStatus(
        { tirPct: 75, tbrPct: 8, cvPct: 25, hadSevereHypo: false },
        7,
        NOW
      );
      expect(bucket).toBe("needs_review");
    });

    it("compounding low TIR + unsafe TBR is urgent", () => {
      const { bucket } = classifyCohortStatus(
        { tirPct: 40, tbrPct: 8, cvPct: 25, hadSevereHypo: false },
        7,
        NOW
      );
      expect(bucket).toBe("urgent_review");
    });

    it("any level-2 hypoglycemia is urgent regardless of other metrics", () => {
      const { bucket } = classifyCohortStatus(
        { tirPct: 80, tbrPct: 1, cvPct: 20, hadSevereHypo: true },
        7,
        NOW
      );
      expect(bucket).toBe("urgent_review");
    });

    it("no data resolves to needs_review with a clear reason", () => {
      const { bucket, reason } = classifyCohortStatus(
        { tirPct: null, tbrPct: null, cvPct: null, hadSevereHypo: false },
        7,
        NOW
      );
      expect(bucket).toBe("needs_review");
      expect(reason).toContain("7 days");
    });
  });

  describe("computeStatusDistribution", () => {
    it("counts each patient once across the four buckets", () => {
      const patients = [
        patient("c", "Controlled", [reading(110, 1), reading(120, 2), reading(130, 3)]),
        patient("w", "Watch", [reading(110, 1), reading(120, 2), reading(130, 3), reading(200, 4), reading(210, 5)]),
        patient("n", "Needs", [reading(110, 1), reading(120, 2), reading(130, 3), reading(65, 4), reading(68, 5)]),
        patient("u", "Urgent", [reading(150, 1), reading(160, 2), reading(40, 3)]),
      ];
      const dist = computeStatusDistribution(patients, 7, NOW);
      expect(dist.controlled).toBe(1);
      expect(dist.watch).toBe(1);
      expect(dist.needsReview).toBe(1);
      expect(dist.urgentReview).toBe(1);
      expect(dist.analyzed).toBe(4);
    });
  });

  describe("computeMonitoringDistribution", () => {
    it("applies the 70% coverage rule for up-to-date status", () => {
      const sevenDays = Array.from({ length: 7 }, (_, i) => reading(120, i + 1));
      const sparseDays = [reading(120, 1), reading(120, 2)];
      const empty = patient("e", "Empty", [reading(120, 60)]);
      const dist = computeMonitoringDistribution([patient("a", "A", sevenDays), patient("b", "B", sparseDays), empty], 7, NOW);
      expect(dist.upToDate).toBe(1);
      expect(dist.limited).toBe(1);
      expect(dist.noRecentData).toBe(1);
      expect(dist.analyzed).toBe(3);
    });
  });

  describe("compareCohortTrends", () => {
    it("detects an improving mean between current and previous windows", () => {
      const current = [reading(100, 2, 12), reading(105, 1, 12)];
      const previous = [reading(200, 9, 12), reading(210, 8, 12)];
      const trend = compareCohortTrends([patient("A", "A", [...current, ...previous])], 7, NOW);
      expect(trend.mean.current).toBe(102.5);
      expect(trend.mean.previous).toBe(205);
      expect(trend.mean.delta).toBeLessThan(0);
      expect(trend.mean.direction).toBe("improving");
    });
  });

  describe("groupCareGapTasks", () => {
    it("groups open tasks by category and ignores completed ones", () => {
      const tasks = [
        { description: "Review latest A1C result", status: "open" },
        { description: "Encourage daily foot inspection", status: "in_progress" },
        { description: "Retinal screening referral", status: "done" },
        { description: "Diet counselling", status: "open" },
      ];
      const gaps = groupCareGapTasks(tasks);
      expect(gaps.a1c).toBe(1);
      expect(gaps.foot).toBe(1);
      expect(gaps.retinal).toBe(0);
      expect(gaps.other).toBe(1);
      expect(gaps.total).toBe(3);
      expect(gaps.matched).toBe(true);
    });
  });

  describe("summarizeReviewQueue", () => {
    it("counts known kinds and buckets the rest as other, sorted by volume", () => {
      const rows = summarizeReviewQueue([
        { artifact_kind: "meal_review" },
        { artifact_kind: "meal_review" },
        { artifact_kind: "glucose_review" },
        { artifact_kind: "custom_kind" },
      ]);
      expect(rows[0]).toEqual({ key: "meal_review", label: "Meal Analysis", count: 2 });
      expect(rows.find((r) => r.key === "other")?.count).toBe(1);
      // First element must be the highest-volume known kind
      expect(rows[0]?.count).toBe(2);
    });

    it("returns an empty list when the queue is empty", () => {
      expect(summarizeReviewQueue([])).toEqual([]);
    });
  });

  it("exposes the ADA/EASD grounding constants", () => {
    expect(ADA_EASD_TARGETS.rangeMinMgDl).toBe(70);
    expect(ADA_EASD_TARGETS.rangeMaxMgDl).toBe(180);
    expect(ADA_EASD_TARGETS.tirTargetPct).toBe(70);
    expect(ADA_EASD_TARGETS.tbrTargetPct).toBe(4);
    expect(ADA_EASD_TARGETS.cvTargetPct).toBe(36);
    expect(ADA_EASD_TARGETS.severeHypoTresholdMgDl).toBe(54);
  });
});