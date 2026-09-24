/**
 * Cohort Clinical Analysis — Doctor Home Command Center (read-model only).
 *
 * Pure, deterministic, read-only aggregation over REAL clinician glucose
 * observations. Nothing here invents a clinical risk score; every flag and
 * category maps to the deterministic thresholds the platform already uses:
 *
 *   - ADA / EASD 70–180 mg/dL target range
 *   - TIR target ≥ 70% ("Optimal" >= 70%, "Suboptimal" 50–70, "Low" < 50)
 *   - TBR target < 4% (TBR > 4% flags hypoglycemia risk)
 *   - CV target ≤ 36% ("STABLE" <= 36%, "HIGH_VARIABILITY" > 36%)
 *   - Level-2 hypoglycemia < 54 mg/dL
 *   - Coverage "continuous" when logged days >= 70% of the window
 *     (mirrors calculateDataCoverage in deterministicIntelligence.ts)
 *
 * These thresholds already live in the platform:
 *   backend/application/services/clinical_calculator.py and the mobile
 *   src/services/clinical/deterministicIntelligence.ts. They are duplicated
 *   only as quoted constants below so the read model stays dependency-light
 *   and testable; they are NOT new medical thresholds.
 */

import { calculateGlycemicMetrics, type GlucoseInputObservation } from "./deterministicIntelligence";

export const ADA_EASD_TARGETS = {
  rangeMinMgDl: 70,
  rangeMaxMgDl: 180,
  tirTargetPct: 70,
  tirSuboptimalPct: 50,
  tbrTargetPct: 4,
  cvTargetPct: 36,
  severeHypoTresholdMgDl: 54,
  coverageContinuousRatio: 0.7,
  periodToleranceDays: 2,
} as const;

/**
 * Home dashboard analyzes at most this many most-recent active patients for
 * cohort metrics. Keeps the read path bounded; the count is always surfaced
 * next to cohort aggregates (sample size) and never masked.
 */
export const COHORT_ANALYSIS_LIMIT = 12;

export const REVIEW_KIND_LABELS: Record<string, string> = {
  meal_review: "Meal Analysis",
  glucose_review: "Glucose Patterns",
  report_summary: "Reports",
};

export interface CohortClientReading {
  value_mg_dl: number | null;
  taken_at: string;
  tag?: string | null;
}

export interface CohortPatientReadings {
  patientId: string;
  name: string;
  uh_id: string;
  readings: CohortClientReading[];
}

export interface CohortMetrics {
  sampleSize: number;
  patientCount: number;
  tirPct: number | null;
  tarPct: number | null;
  tbrPct: number | null;
  meanMgDl: number | null;
  gmiPct: number | null;
  cvPct: number | null;
  readingCount: number;
  lastReadingAt: string | null;
}

export type AttentionSeverity = "needs_review" | "observing";

export interface AttentionFlag {
  severity: AttentionSeverity;
  label: string;
  detail: string;
}

export type CohortStatusBucket =
  | "controlled"
  | "watch"
  | "needs_review"
  | "urgent_review";

export type MonitoringBucket = "up_to_date" | "limited" | "no_recent_data";

export type TrendDirection = "improving" | "stable" | "deteriorating";

const DAY_MS = 24 * 60 * 60 * 1000;

export function nowIso(): string {
  return new Date().toISOString();
}

function isReadingInWindow(reading: CohortClientReading, now: number, days: number): boolean {
  const t = new Date(reading.taken_at).getTime();
  if (Number.isNaN(t)) return false;
  return t >= now - days * DAY_MS && t <= now;
}

function validValues(readings: CohortClientReading[]): number[] {
  return readings
    .map((r) => r.value_mg_dl)
    .filter((v): v is number => typeof v === "number" && !Number.isNaN(v) && v > 0);
}

function toMetricObservations(readings: CohortClientReading[]): GlucoseInputObservation[] {
  return readings
    .filter((r) => typeof r.value_mg_dl === "number" && !Number.isNaN(r.value_mg_dl) && r.value_mg_dl > 0)
    .map((r) => ({
      value_mg_dl: r.value_mg_dl as number,
      taken_at: r.taken_at,
      tag: r.tag ?? null,
    }));
}

/**
 * Filters a patient's readings to the trailing `days` window, newest first.
 */
export function filterReadingsInWindow(
  readings: CohortClientReading[],
  days: number,
  now: number = Date.now()
): CohortClientReading[] {
  return readings
    .filter((r) => isReadingInWindow(r, now, days))
    .sort((a, b) => new Date(a.taken_at).getTime() - new Date(b.taken_at).getTime());
}

function roundTo(value: number, decimals: number = 1): number {
  const factor = Math.pow(10, decimals);
  return Math.round(value * factor) / factor;
}

function avg(nums: number[]): number | null {
  if (nums.length === 0) return null;
  return nums.reduce((a, b) => a + b, 0) / nums.length;
}

function meanOfNullable(values: (number | null)[]): number | null {
  const present = values.filter((v): v is number => v !== null && !Number.isNaN(v));
  return avg(present);
}

/**
 * Aggregates per-patient ADA/EASD metrics into cohort-level "average of
 * patients with data" figures. Each analyzed patient contributes once,
 * regardless of reading volume, so no single heavily-logged patient skews
 * the cohort numbers. `sampleSize` tracks how many patients actually had
 * data within the window.
 */
export function aggregateCohortMetrics(
  patients: CohortPatientReadings[],
  days: number,
  now: number = Date.now()
): CohortMetrics {
  const patientCount = patients.length;
  const tir: number[] = [];
  const tar: number[] = [];
  const tbr: number[] = [];
  const means: number[] = [];
  const gmis: number[] = [];
  const cvs: number[] = [];
  let readingCount = 0;
  let lastReadingAt: string | null = null;

  for (const patient of patients) {
    const windowed = filterReadingsInWindow(patient.readings, days, now);
    if (windowed.length === 0) continue;
    readingCount += windowed.length;
    for (const r of windowed) {
      if (r.taken_at && (lastReadingAt === null || r.taken_at > lastReadingAt)) {
        lastReadingAt = r.taken_at;
      }
    }
    const metrics = calculateGlycemicMetrics(toMetricObservations(windowed), days);
    if (metrics.timeInRangePct !== null) tir.push(metrics.timeInRangePct);
    if (metrics.timeAboveRangePct !== null) tar.push(metrics.timeAboveRangePct);
    if (metrics.timeBelowRangePct !== null) tbr.push(metrics.timeBelowRangePct);
    if (metrics.meanMgDl !== null) means.push(metrics.meanMgDl);
    if (metrics.gmiPct !== null) gmis.push(metrics.gmiPct);
    if (metrics.coefficientOfVariationPct !== null) cvs.push(metrics.coefficientOfVariationPct);
  }

  const sampleSize = tir.length;
  const round = (v: number | null): number | null => (v === null ? null : roundTo(v));
  return {
    sampleSize,
    patientCount,
    tirPct: round(meanOfNullable(tir)),
    tarPct: round(meanOfNullable(tar)),
    tbrPct: round(meanOfNullable(tbr)),
    meanMgDl: round(meanOfNullable(means)),
    gmiPct: round(meanOfNullable(gmis)),
    cvPct: round(meanOfNullable(cvs)),
    readingCount,
    lastReadingAt,
  };
}

/**
 * Builds a per-day cohort-average glucose series (pooled readings per calendar
 * day across the analyzed patients). Ordered oldest → newest. Days with no
 * data are omitted so the trend never fabricates a reading.
 */
export function buildDailyMeanSeries(
  patients: CohortPatientReadings[],
  days: number,
  now: number = Date.now()
): { label: string; value: number; dayStart: number }[] {
  const byDay = new Map<string, { dayStart: number; values: number[] }>();
  for (const patient of patients) {
    for (const r of filterReadingsInWindow(patient.readings, days, now)) {
      const v = r.value_mg_dl;
      if (typeof v !== "number" || Number.isNaN(v) || v <= 0) continue;
      const t = new Date(r.taken_at).getTime();
      if (Number.isNaN(t)) continue;
      const dayKey = new Date(t).toISOString().slice(0, 10);
      const dayStart = new Date(`${dayKey}T00:00:00.000Z`).getTime();
      const entry = byDay.get(dayKey) ?? { dayStart, values: [] };
      entry.values.push(v);
      byDay.set(dayKey, entry);
    }
  }
  return [...byDay.entries()]
    .map(([dayKey, entry]) => ({
      label: dayKey,
      value: roundTo(avg(entry.values) ?? 0),
      dayStart: entry.dayStart,
    }))
    .sort((a, b) => a.dayStart - b.dayStart);
}

/**
 * Mean glucose for the trailing `days` window across the cohort (pooled).
 */
export function cohortPeriodMeanMgDl(
  patients: CohortPatientReadings[],
  days: number,
  now: number = Date.now()
): number | null {
  const values: number[] = [];
  for (const patient of patients) {
    for (const r of filterReadingsInWindow(patient.readings, days, now)) {
      if (typeof r.value_mg_dl === "number" && r.value_mg_dl > 0) values.push(r.value_mg_dl);
    }
  }
  const m = avg(values);
  return m === null ? null : roundTo(m);
}

/**
 * Identifies evidence-based, human-readable attention flags for one patient.
 * Every flag cites the observed metric and the platform target — no invented
 * risk scores, no unexplained clinical judgments.
 */
export function deriveAttentionFlags(
  patient: CohortPatientReadings,
  days: number,
  now: number = Date.now()
): AttentionFlag[] {
  const windowed = filterReadingsInWindow(patient.readings, days, now);
  const flags: AttentionFlag[] = [];

  if (windowed.length === 0) {
    return [
      {
        severity: "needs_review",
        label: "No recent glucose data",
        detail: `No readings recorded for ${patient.name} in the last ${days} days.`,
      },
    ];
  }

  const metrics = calculateGlycemicMetrics(toMetricObservations(windowed), days);
  const values = validValues(windowed);

  if (metrics.timeInRangePct !== null && metrics.timeInRangePct < ADA_EASD_TARGETS.tirSuboptimalPct) {
    flags.push({
      severity: "needs_review",
      label: "Reduced time in range",
      detail: `TIR ${metrics.timeInRangePct}% in the last ${days} days (target ≥ ${ADA_EASD_TARGETS.tirTargetPct}%).`,
    });
  }

  if (metrics.timeBelowRangePct !== null && metrics.timeBelowRangePct > ADA_EASD_TARGETS.tbrTargetPct) {
    flags.push({
      severity: "needs_review",
      label: "Repeated hypoglycemia",
      detail: `TBR ${metrics.timeBelowRangePct}% (target < ${ADA_EASD_TARGETS.tbrTargetPct}%).`,
    });
  }

  const minValue = Math.min(...values);
  if (minValue < ADA_EASD_TARGETS.severeHypoTresholdMgDl) {
    flags.push({
      severity: "needs_review",
      label: "Severe hypoglycemia reading",
      detail: `A reading of ${Math.round(minValue)} mg/dL was recorded (< ${ADA_EASD_TARGETS.severeHypoTresholdMgDl} mg/dL).`,
    });
  }

  if (metrics.coefficientOfVariationPct !== null && metrics.coefficientOfVariationPct > ADA_EASD_TARGETS.cvTargetPct) {
    flags.push({
      severity: "needs_review",
      label: "High glycemic variability",
      detail: `CV ${metrics.coefficientOfVariationPct}% (target ≤ ${ADA_EASD_TARGETS.cvTargetPct}%).`,
    });
  }

  const dawnSuspected = detectDawnPhenomenon(windowed);
  if (dawnSuspected) {
    flags.push({
      severity: "observing",
      label: "Possible dawn phenomenon",
      detail: "At least two fasting readings ≥ 130 mg/dL without nocturnal hypoglycemia were observed.",
    });
  }

  const currentMean = metrics.meanMgDl;
  const previousMean = cohortPreviousPeriodMeanMgDl(patient.readings, days, now);
  if (
    currentMean !== null &&
    previousMean !== null &&
    currentMean >= previousMean + ADA_EASD_TARGETS.periodToleranceDays * 5
  ) {
    flags.push({
      severity: "observing",
      label: "Mean glucose increasing",
      detail: `Mean glucose rose from ${previousMean} to ${currentMean} mg/dL across the compared periods.`,
    });
  }

  return flags;
}

/**
 * Compares the trailing `days` window mean with the immediately preceding
 * equal-length window (descriptive, non-causal).
 */
export function cohortPreviousPeriodMeanMgDl(
  readings: CohortClientReading[],
  days: number,
  now: number = Date.now()
): number | null {
  const start = now - 2 * days * DAY_MS;
  const end = now - days * DAY_MS;
  const values = readings
    .filter((r) => {
      const t = new Date(r.taken_at).getTime();
      return !Number.isNaN(t) && t >= start && t <= end;
    })
    .map((r) => r.value_mg_dl)
    .filter((v): v is number => typeof v === "number" && v > 0);
  const m = avg(values);
  return m === null ? null : roundTo(m);
}

function detectDawnPhenomenon(readings: CohortClientReading[]): boolean {
  const fasting: number[] = [];
  let nocturnalHypo = false;
  for (const r of readings) {
    const v = r.value_mg_dl;
    if (typeof v !== "number" || v <= 0) continue;
    const hour = new Date(r.taken_at).getHours();
    if (hour >= 3 && hour < 9) {
      const tag = (r.tag ?? "").toLowerCase();
      if (tag.includes("fast") || hour >= 4) fasting.push(v);
    }
    if (v < ADA_EASD_TARGETS.rangeMinMgDl && hour >= 22) nocturnalHypo = true;
  }
  return fasting.filter((v) => v >= 130).length >= 2 && !nocturnalHypo;
}

/**
 * Maps per-patient metrics onto the four cohort-status buckets using only the
 * platform's established thresholds (TIR/TBR/CV + level-2 hypoglycemia).
 */
export function classifyCohortStatus(
  indicators: { tirPct: number | null; tbrPct: number | null; cvPct: number | null; hadSevereHypo: boolean },
  days: number,
  now: number = Date.now()
): { bucket: CohortStatusBucket; reason: string } {
  const { tirPct, tbrPct, cvPct, hadSevereHypo } = indicators;
  if (tirPct === null && tbrPct === null && cvPct === null) {
    return {
      bucket: "needs_review",
      reason: `No glucose data available in the last ${days} days.`,
    };
  }

  const tirOk = tirPct === null || tirPct >= ADA_EASD_TARGETS.tirTargetPct;

  if (hadSevereHypo) {
    return { bucket: "urgent_review", reason: "Level-2 hypoglycemia (< 54 mg/dL) recorded." };
  }

  const lowTir = tirPct !== null && tirPct < ADA_EASD_TARGETS.tirSuboptimalPct;
  const suboptimalTir = tirPct !== null && tirPct < ADA_EASD_TARGETS.tirTargetPct;
  const tbrUnsafe = tbrPct !== null && tbrPct > ADA_EASD_TARGETS.tbrTargetPct;
  const cvUnsafe = cvPct !== null && cvPct > ADA_EASD_TARGETS.cvTargetPct;

  if (lowTir && (tbrUnsafe || cvUnsafe)) {
    return {
      bucket: "urgent_review",
      reason: `Low TIR ${tirPct}% combined with ${tbrUnsafe ? "elevated TBR" : "high variability"}.`,
    };
  }

  if (lowTir || tbrUnsafe || cvUnsafe) {
    const parts = [
      lowTir ? `TIR ${tirPct}%` : null,
      tbrUnsafe ? `TBR ${tbrPct}%` : null,
      cvUnsafe ? `CV ${cvPct}%` : null,
    ].filter(Boolean);
    return { bucket: "needs_review", reason: `${parts.join(" · ")} outside targets.` };
  }

  if (!tirOk && suboptimalTir) {
    return { bucket: "watch", reason: `Suboptimal TIR ${tirPct}% (target ≥ ${ADA_EASD_TARGETS.tirTargetPct}%).` };
  }

  return { bucket: "controlled", reason: "Glycemic targets met in the analysis period." };
}

export function computeStatusDistribution(
  patients: CohortPatientReadings[],
  days: number,
  now: number = Date.now()
): { controlled: number; watch: number; needsReview: number; urgentReview: number; analyzed: number } {
  let controlled = 0;
  let watch = 0;
  let needsReview = 0;
  let urgentReview = 0;
  let analyzed = 0;

  for (const patient of patients) {
    const windowed = filterReadingsInWindow(patient.readings, days, now);
    const values = validValues(windowed);
    const metrics = calculateGlycemicMetrics(toMetricObservations(windowed), days);
    const hadSevereHypo = values.some((v) => v < ADA_EASD_TARGETS.severeHypoTresholdMgDl);
    analyzed += 1;
    const { bucket } = classifyCohortStatus(
      {
        tirPct: metrics.timeInRangePct,
        tbrPct: metrics.timeBelowRangePct,
        cvPct: metrics.coefficientOfVariationPct,
        hadSevereHypo,
      },
      days,
      now
    );
    if (bucket === "controlled") controlled += 1;
    else if (bucket === "watch") watch += 1;
    else if (bucket === "needs_review") needsReview += 1;
    else urgentReview += 1;
  }

  return { controlled, watch, needsReview, urgentReview, analyzed };
}

/**
 * Monitoring / data-quality distribution reusing the platform's "continuous"
 * rule (logged days >= 70% of the window). "No recent data" is unambiguous
 * (zero logged days in window); partial coverage is "limited data".
 */
export function computeMonitoringDistribution(
  patients: CohortPatientReadings[],
  days: number,
  now: number = Date.now()
): { upToDate: number; limited: number; noRecentData: number; analyzed: number } {
  let upToDate = 0;
  let limited = 0;
  let noRecentData = 0;

  for (const patient of patients) {
    const activeDays = new Set(
      filterReadingsInWindow(patient.readings, days, now).map((r) => r.taken_at.slice(0, 10))
    ).size;
    const ratio = days > 0 ? activeDays / days : 0;
    if (activeDays === 0) noRecentData += 1;
    else if (ratio >= ADA_EASD_TARGETS.coverageContinuousRatio) upToDate += 1;
    else limited += 1;
  }

  return { upToDate, limited, noRecentData, analyzed: patients.length };
}

export interface TrendComparisons {
  tir: { current: number | null; previous: number | null; delta: number | null; direction: TrendDirection };
  mean: { current: number | null; previous: number | null; delta: number | null; direction: TrendDirection };
  gmi: { current: number | null; previous: number | null; delta: number | null; direction: TrendDirection };
  tbr: { current: number | null; previous: number | null; delta: number | null; direction: TrendDirection };
  cv: { current: number | null; previous: number | null; delta: number | null; direction: TrendDirection };
}

/**
 * Compares current-window vs previous equal-length window for the five key
 * cohort metrics. Direction is always relative to the platform targets
 * (TIR higher is better; TBR / CV / mean / GMI lower is better). "stable"
 * means the change is within a clinically quiet tolerance.
 */
export function compareCohortTrends(
  patients: CohortPatientReadings[],
  days: number,
  now: number = Date.now()
): TrendComparisons {
  const current = aggregateCohortMetrics(patients, days, now);
  const previous = aggregateCohortMetrics(patients, days, now - days * DAY_MS);

  const delta = (cur: number | null, prev: number | null): number | null => {
    if (cur === null || prev === null) return null;
    return roundTo(cur - prev, 1);
  };

  const directionFor = (
    cur: number | null,
    prev: number | null,
    goodDirection: "up" | "down"
  ): TrendDirection => {
    if (cur === null || prev === null || Math.abs(cur - prev) < 0.05) return "stable";
    const rising = cur >= prev;
    if (rising === (goodDirection === "up")) return "improving";
    return "deteriorating";
  };

  const d = {
    tir: delta(current.tirPct, previous.tirPct),
    mean: delta(current.meanMgDl, previous.meanMgDl),
    gmi: delta(current.gmiPct, previous.gmiPct),
    tbr: delta(current.tbrPct, previous.tbrPct),
    cv: delta(current.cvPct, previous.cvPct),
  };

  return {
    tir: {
      current: current.tirPct,
      previous: previous.tirPct,
      delta: d.tir,
      direction: directionFor(current.tirPct, previous.tirPct, "up"),
    },
    mean: {
      current: current.meanMgDl,
      previous: previous.meanMgDl,
      delta: d.mean,
      direction: directionFor(current.meanMgDl, previous.meanMgDl, "down"),
    },
    gmi: {
      current: current.gmiPct,
      previous: previous.gmiPct,
      delta: d.gmi,
      direction: directionFor(current.gmiPct, previous.gmiPct, "down"),
    },
    tbr: {
      current: current.tbrPct,
      previous: previous.tbrPct,
      delta: d.tbr,
      direction: directionFor(current.tbrPct, previous.tbrPct, "down"),
    },
    cv: {
      current: current.cvPct,
      previous: previous.cvPct,
      delta: d.cv,
      direction: directionFor(current.cvPct, previous.cvPct, "down"),
    },
  };
}

export interface CareGapCounts {
  a1c: number;
  bloodPressure: number;
  kidney: number;
  retinal: number;
  foot: number;
  lipid: number;
  other: number;
  total: number;
  matched: boolean;
}

/**
 * Groups the clinician's REAL open / in-progress care tasks by diabetes
 * care-gap category via conservative keyword matching on task descriptions.
 * This is a data-quality grouping of existing work items — it never assigns
 * a care gap the doctor did not actually create.
 */
export function groupCareGapTasks(
  tasks: {
    description: string;
    status: string;
  }[]
): CareGapCounts {
  const counts: CareGapCounts = {
    a1c: 0,
    bloodPressure: 0,
    kidney: 0,
    retinal: 0,
    foot: 0,
    lipid: 0,
    other: 0,
    total: 0,
    matched: false,
  };

  const active = tasks.filter((t) => t.status === "open" || t.status === "in_progress");

  const rules: { key: keyof Omit<CareGapCounts, "total" | "matched">; terms: string[] }[] = [
    { key: "a1c", terms: ["a1c", "hba1c", "glycated", "hemoglobin", "hb a1c"] },
    { key: "bloodPressure", terms: ["blood pressure", "bp ", "hypertension", "systolic"] },
    { key: "kidney", terms: ["kidney", "renal", "egfr", "uacr", "albumin", "creatinine", "microalbumin"] },
    { key: "retinal", terms: ["retinal", "retina", "eye", "fundus", "diabetic retinopathy"] },
    { key: "foot", terms: ["foot", "feet", "sensory", "monofilament", "ulcer"] },
    { key: "lipid", terms: ["lipid", "cholesterol", "ldl", "hdl", "triglyceride"] },
  ];

  for (const task of active) {
    const text = task.description.toLowerCase().trim();
    let matched = false;
    for (const rule of rules) {
      if (rule.terms.some((term) => text.includes(term))) {
        const key = rule.key;
        counts[key] += 1;
        counts.total += 1;
        matched = true;
        break;
      }
    }
    if (!matched) {
      counts.other += 1;
      counts.total += 1;
    }
  }

  counts.matched = counts.a1c + counts.bloodPressure + counts.kidney + counts.retinal + counts.foot + counts.lipid > 0;
  return counts;
}

export function summarizeReviewQueue(
  queue: { artifact_kind: string }[]
): { key: string; label: string; count: number }[] {
  const byKind = new Map<string, number>();
  for (const item of queue) {
    byKind.set(item.artifact_kind, (byKind.get(item.artifact_kind) ?? 0) + 1);
  }
  const rows: { key: string; label: string; count: number }[] = [];
  for (const [kind, count] of byKind.entries()) {
    const label = REVIEW_KIND_LABELS[kind];
    if (label) {
      rows.push({ key: kind, label, count });
    }
  }
  const remaining =
    queue.length - rows.reduce((sum, row) => sum + row.count, 0);
  if (remaining > 0) {
    rows.push({ key: "other", label: "Other observations", count: remaining });
  }
  return rows.sort((a, b) => b.count - a.count);
}