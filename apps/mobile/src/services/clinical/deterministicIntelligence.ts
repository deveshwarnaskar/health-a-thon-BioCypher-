/**
 * Deterministic Clinical Intelligence Layer (Section 5.2, 18, 19, 20, 21, 27).
 *
 * Implements pure, deterministic mathematical and statistical calculations for:
 * - Glycemic Metrics (TIR, TBR, TAR, Mean, Median, SD, CV, GMI, eAG)
 * - Personal Baseline Engine (rolling median, MAD, descriptive baseline deviations)
 * - Temporal Alignment (meal-to-glucose time deltas with non-causal language)
 * - Data Coverage Summary (descriptive completeness, never a clinical risk score)
 *
 * CLINICAL SAFETY INVARIANTS:
 * 1. Independent from any LLM or black-box inference.
 * 2. Purely deterministic and versioned.
 * 3. Never generates autonomous diagnoses, clinical risk scores, or medication changes.
 * 4. All contextual relations use non-causal descriptive wording ("Observed association").
 */

export const DETERMINISTIC_INTELLIGENCE_VERSION = "1.0.0-deterministic-ada-easd-2019";

export interface GlucoseInputObservation {
  id?: string;
  value_mg_dl: number;
  taken_at: string;
  tag?: string | null;
}

export interface MealInputObservation {
  id?: string;
  description: string;
  recorded_at: string;
  portion_label?: string | null;
  carbs_grams?: number | null;
}

export interface GlycemicMetricsResult {
  version: string;
  calculatedAt: string;
  periodDays: number;
  totalObservations: number;
  meanMgDl: number | null;
  medianMgDl: number | null;
  standardDeviationMgDl: number | null;
  coefficientOfVariationPct: number | null;
  timeInRangePct: number | null; // 70-180 mg/dL
  timeBelowRangePct: number | null; // <70 mg/dL
  timeAboveRangePct: number | null; // >180 mg/dL
  gmiPct: number | null; // Glucose Management Indicator: 3.31 + 0.02392 * mean (%)
  estimatedA1cPct: number | null; // Estimated A1c via ADAG: (mean + 46.7) / 28.7 (%)
  readingCountByTag: Record<string, number>;
  interpretationSummary: string;
}

export interface PersonalBaselineResult {
  windowDays: number;
  medianMgDl: number | null;
  madMgDl: number | null; // Median Absolute Deviation
  baselineRange: { low: number; high: number } | null;
  descriptiveNote: string;
}

export interface TemporalAlignmentItem {
  mealId?: string;
  mealDescription: string;
  mealRecordedAt: string;
  glucoseId?: string;
  glucoseMgDl: number;
  glucoseTakenAt: string;
  deltaMinutes: number;
  windowLabel: string;
  relationshipNote: string;
}

export interface DataCoverageResult {
  evaluationWindowDays: number;
  activeLoggedDays: number;
  coverageRatio: number;
  coverageText: string;
  glucoseReadingCount: number;
  mealRecordCount: number;
  isContinuous: boolean;
}

function computeMedian(sortedNumbers: number[]): number {
  if (sortedNumbers.length === 0) return 0;
  const mid = Math.floor(sortedNumbers.length / 2);
  const midVal = sortedNumbers[mid] ?? 0;
  if (sortedNumbers.length % 2 !== 0) {
    return midVal;
  }
  const prevVal = sortedNumbers[mid - 1] ?? midVal;
  return (prevVal + midVal) / 2;
}

/**
 * Calculates deterministic glycemic metrics from a sequence of observations.
 * Targets: 70 - 180 mg/dL (ADA/EASD consensus standards).
 */
export function calculateGlycemicMetrics(
  observations: GlucoseInputObservation[],
  periodDays: number = 14
): GlycemicMetricsResult {
  const calculatedAt = new Date().toISOString();
  const valid = observations
    .map((o) => o.value_mg_dl)
    .filter((v) => typeof v === "number" && !isNaN(v) && v > 0);

  if (valid.length === 0) {
    return {
      version: DETERMINISTIC_INTELLIGENCE_VERSION,
      calculatedAt,
      periodDays,
      totalObservations: 0,
      meanMgDl: null,
      medianMgDl: null,
      standardDeviationMgDl: null,
      coefficientOfVariationPct: null,
      timeInRangePct: null,
      timeBelowRangePct: null,
      timeAboveRangePct: null,
      gmiPct: null,
      estimatedA1cPct: null,
      readingCountByTag: {},
      interpretationSummary: "Insufficient observation data for deterministic glycemic calculation.",
    };
  }

  // 1. Mean
  const sum = valid.reduce((acc, val) => acc + val, 0);
  const mean = sum / valid.length;

  // 2. Median
  const sorted = [...valid].sort((a, b) => a - b);
  const median = computeMedian(sorted);

  // 3. Standard Deviation (sample SD if n > 1)
  let sd = 0;
  if (valid.length > 1) {
    const variance = valid.reduce((acc, val) => acc + Math.pow(val - mean, 2), 0) / (valid.length - 1);
    sd = Math.sqrt(variance);
  }

  // 4. Coefficient of Variation (CV % = SD / Mean * 100)
  const cv = mean > 0 ? (sd / mean) * 100 : 0;

  // 5. Time in Ranges
  const inRangeCount = valid.filter((v) => v >= 70 && v <= 180).length;
  const belowRangeCount = valid.filter((v) => v < 70).length;
  const aboveRangeCount = valid.filter((v) => v > 180).length;

  const tir = (inRangeCount / valid.length) * 100;
  const tbr = (belowRangeCount / valid.length) * 100;
  const tar = (aboveRangeCount / valid.length) * 100;

  // 6. GMI (Glucose Management Indicator in %)
  const gmi = 3.31 + 0.02392 * mean;

  // 7. Estimated A1c via ADAG regression: (mean + 46.7) / 28.7 in %
  const estimatedA1c = (mean + 46.7) / 28.7;

  // 8. Tag distribution
  const tagCounts: Record<string, number> = {};
  for (const obs of observations) {
    const tag = (obs.tag || "unspecified").toLowerCase();
    tagCounts[tag] = (tagCounts[tag] || 0) + 1;
  }

  // Summary note: purely descriptive
  const interpretationSummary = `Calculated over ${valid.length} observations (${periodDays}-day window): Time-in-range is ${tir.toFixed(1)}%, with mean glucose of ${Math.round(mean)} mg/dL.`;

  return {
    version: DETERMINISTIC_INTELLIGENCE_VERSION,
    calculatedAt,
    periodDays,
    totalObservations: valid.length,
    meanMgDl: Math.round(mean * 10) / 10,
    medianMgDl: Math.round(median * 10) / 10,
    standardDeviationMgDl: Math.round(sd * 10) / 10,
    coefficientOfVariationPct: Math.round(cv * 10) / 10,
    timeInRangePct: Math.round(tir * 10) / 10,
    timeBelowRangePct: Math.round(tbr * 10) / 10,
    timeAboveRangePct: Math.round(tar * 10) / 10,
    gmiPct: Math.round(gmi * 10) / 10,
    estimatedA1cPct: Math.round(estimatedA1c * 10) / 10,
    readingCountByTag: tagCounts,
    interpretationSummary,
  };
}

/**
 * Calculates a rolling personal baseline using robust statistics (median & MAD).
 * Section 19: descriptive output only, never diagnostic or prescriptive.
 */
export function calculatePersonalBaseline(
  observations: GlucoseInputObservation[],
  windowDays: number = 14
): PersonalBaselineResult {
  const values = observations.map((o) => o.value_mg_dl).filter((v) => v > 0);
  if (values.length < 3) {
    return {
      windowDays,
      medianMgDl: null,
      madMgDl: null,
      baselineRange: null,
      descriptiveNote: "Insufficient history to establish personal baseline profile.",
    };
  }

  const sorted = [...values].sort((a, b) => a - b);
  const median = computeMedian(sorted);

  // Median Absolute Deviation (MAD)
  const deviations = sorted.map((v) => Math.abs(v - median)).sort((a, b) => a - b);
  const mad = computeMedian(deviations);

  // Expected descriptive range (~1.5 * MAD from median)
  const low = Math.max(50, Math.round(median - 1.5 * mad));
  const high = Math.round(median + 1.5 * mad);

  return {
    windowDays,
    medianMgDl: Math.round(median),
    madMgDl: Math.round(mad),
    baselineRange: { low, high },
    descriptiveNote: `Personal ${windowDays}-day median baseline is ${Math.round(median)} mg/dL (typical window: ${low}–${high} mg/dL).`,
  };
}

/**
 * Computes temporal alignment between meals and adjacent glucose observations.
 * Section 20 & 21: Preserves observed association language, avoids causal claims.
 */
export function calculateTemporalAlignment(
  meals: MealInputObservation[],
  glucoseReadings: GlucoseInputObservation[],
  maxWindowMinutes: number = 240
): TemporalAlignmentItem[] {
  const alignments: TemporalAlignmentItem[] = [];

  for (const meal of meals) {
    const mealTime = new Date(meal.recorded_at).getTime();
    if (isNaN(mealTime)) continue;

    for (const reading of glucoseReadings) {
      const glucoseTime = new Date(reading.taken_at).getTime();
      if (isNaN(glucoseTime)) continue;

      const deltaMs = glucoseTime - mealTime;
      const deltaMinutes = Math.round(deltaMs / (60 * 1000));

      // Consider readings within -30 min (pre-prandial) to +240 min (post-prandial)
      if (deltaMinutes >= -30 && deltaMinutes <= maxWindowMinutes) {
        let windowLabel: string;
        if (deltaMinutes < 0) {
          windowLabel = `Pre-meal (${Math.abs(deltaMinutes)}m prior)`;
        } else if (deltaMinutes <= 60) {
          windowLabel = `1h Post-meal (+${deltaMinutes}m)`;
        } else if (deltaMinutes <= 120) {
          windowLabel = `2h Post-meal (+${deltaMinutes}m)`;
        } else {
          windowLabel = `Late post-meal (+${deltaMinutes}m)`;
        }

        alignments.push({
          mealId: meal.id,
          mealDescription: meal.description,
          mealRecordedAt: meal.recorded_at,
          glucoseId: reading.id,
          glucoseMgDl: reading.value_mg_dl,
          glucoseTakenAt: reading.taken_at,
          deltaMinutes,
          windowLabel,
          relationshipNote: `Observed reading of ${reading.value_mg_dl} mg/dL at ${windowLabel} relative to ${meal.description}.`,
        });
      }
    }
  }

  // Sort by meal recorded time descending
  return alignments.sort(
    (a, b) => new Date(b.mealRecordedAt).getTime() - new Date(a.mealRecordedAt).getTime()
  );
}

/**
 * Evaluates patient data coverage over a requested window.
 * Section 17: Displays data presence without generating a clinical risk score.
 */
export function calculateDataCoverage(
  glucoseReadings: GlucoseInputObservation[],
  meals: MealInputObservation[],
  requestedDays: number = 14
): DataCoverageResult {
  const now = new Date();
  const cutoffTime = now.getTime() - requestedDays * 24 * 60 * 60 * 1000;

  const loggedDaySet = new Set<string>();

  for (const g of glucoseReadings) {
    const t = new Date(g.taken_at).getTime();
    if (t >= cutoffTime) {
      loggedDaySet.add(new Date(g.taken_at).toISOString().slice(0, 10));
    }
  }

  for (const m of meals) {
    const t = new Date(m.recorded_at).getTime();
    if (t >= cutoffTime) {
      loggedDaySet.add(new Date(m.recorded_at).toISOString().slice(0, 10));
    }
  }

  const activeLoggedDays = loggedDaySet.size;
  const coverageRatio = requestedDays > 0 ? activeLoggedDays / requestedDays : 0;
  const coverageText = `${activeLoggedDays} of requested ${requestedDays} days logged`;

  return {
    evaluationWindowDays: requestedDays,
    activeLoggedDays,
    coverageRatio: Math.round(coverageRatio * 100) / 100,
    coverageText,
    glucoseReadingCount: glucoseReadings.length,
    mealRecordCount: meals.length,
    isContinuous: activeLoggedDays >= requestedDays * 0.7,
  };
}
