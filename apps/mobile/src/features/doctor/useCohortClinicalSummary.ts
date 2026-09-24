import { useMemo } from "react";
import { useQueries } from "@tanstack/react-query";
import { fetchClinicianFeed } from "./api";
import { doctorKeys } from "./doctorKeys";
import { useReviewQueue } from "./useReviewQueue";
import { useCareTasks } from "./useCareTasks";
import {
  COHORT_ANALYSIS_LIMIT,
  aggregateCohortMetrics,
  buildDailyMeanSeries,
  classifyCohortStatus,
  cohortPeriodMeanMgDl,
  cohortPreviousPeriodMeanMgDl,
  compareCohortTrends,
  computeMonitoringDistribution,
  computeStatusDistribution,
  deriveAttentionFlags,
  filterReadingsInWindow,
  groupCareGapTasks,
  summarizeReviewQueue,
  type AttentionFlag,
  type CareGapCounts,
  type CohortMetrics,
  type CohortPatientReadings,
  type CohortStatusBucket,
  type MonitoringBucket,
  type TrendComparisons,
} from "../../services/clinical/cohortClinicalAnalysis";
import type { AIArtifactResponse } from "../../services/schemas/ai";
import type { PatientSummaryResponse } from "../../services/schemas/patients";
import type {
  ClinicianGlucoseObservation,
  ClinicianObservationFeedResponse,
} from "../../services/schemas/clinical";

const FEED_LIMIT = 200;

export type CohortPeriodKey = "7d" | "30d" | "90d";
export type TrendGranularity = "daily" | "weekly" | "monthly";

export const COHORT_PERIOD_DAYS: Record<CohortPeriodKey, number> = {
  "7d": 7,
  "30d": 30,
  "90d": 90,
};

export interface CohortAttentionPatient {
  patient: PatientSummaryResponse;
  flags: AttentionFlag[];
  lastReadingValue: number | null;
  lastReadingAt: string | null;
}

export interface TrendDayPoint {
  label: string;
  value: number;
}

export type UseCohortClinicalSummaryResult = {
  analyzedCount: number;
  totalPatients: number;
  isLoadingFeed: boolean;
  hasFeedErrors: boolean;
  failedPatients: number;
  hasFeedQueriesSettled: boolean;
  latestFeedUpdateAt: number | null;
  refreshCohort: () => Promise<unknown>;

  attentionPatients: CohortAttentionPatient[];

  cohortByPeriod: Record<CohortPeriodKey, CohortMetrics>;
  statusByPeriod: Record<
    CohortPeriodKey,
    { controlled: number; watch: number; needsReview: number; urgentReview: number; analyzed: number }
  >;
  monitoring30d: { upToDate: number; limited: number; noRecentData: number; analyzed: number };
  trendsByPeriod: Record<CohortPeriodKey, TrendComparisons>;

  meanByWindow: Record<CohortPeriodKey, number | null>;
  previousMeanByWindow: Record<CohortPeriodKey, number | null>;
  dailySeriesByWindow: Record<CohortPeriodKey, TrendDayPoint[]>;

  reviewTotal: number;
  reviewKinds: { key: string; label: string; count: number }[];
  reviewQueue: AIArtifactResponse[];
  isReviewLoading: boolean;

  careTaskTotal: number;
  careGaps: CareGapCounts;
  isTasksLoading: boolean;
};

function glucoseReadingsFromFeed(feed: ClinicianObservationFeedResponse | null): CohortPatientReadings["readings"] {
  if (!feed) return [];
  return feed.items
    .filter((item): item is ClinicianGlucoseObservation => item.kind === "glucose")
    .map((item) => ({
      value_mg_dl: item.value_mg_dl ?? null,
      taken_at: item.taken_at,
      tag: item.tag ?? null,
    }));
}

/**
 * Composes the Doctor Home command-center read model from REAL platform
 * endpoints only:
 *   - patient cohort          → usePatients (passed in)
 *   - clinician observations  → fetchClinicianFeed per analyzed patient
 *   - AI review queue         → useReviewQueue
 *   - care tasks              → useCareTasks
 *
 * Feed queries share the exact query keys used by the patient workspace
 * (doctorKeys.clinicianObservations), so navigating into a patient re-uses
 * the cache — no duplicate requests.
 *
 * Cohort metrics intentionally cover at most COHORT_ANALYSIS_LIMIT most-recent
 * active patients; the analyzed count is always surfaced next to aggregates.
 */
export function useCohortClinicalSummary(
  patients: PatientSummaryResponse[]
): UseCohortClinicalSummaryResult {
  const review = useReviewQueue();
  const tasks = useCareTasks();

  const analyzed = useMemo(
    () =>
      patients
        .filter((p) => p.active)
        .slice(0, COHORT_ANALYSIS_LIMIT),
    [patients]
  );

  const feedQueries = useQueries({
    queries: analyzed.map((p) => ({
      queryKey: doctorKeys.clinicianObservations(p.patient_id),
      queryFn: () => fetchClinicianFeed(p.patient_id, FEED_LIMIT),
      staleTime: 30_000,
      retry: 1,
    })),
  });

  const readingSets = useMemo<CohortPatientReadings[]>(() => {
    return analyzed.map((patient, index) => ({
      patientId: patient.patient_id,
      name: patient.name,
      uh_id: patient.uh_id,
      readings: glucoseReadingsFromFeed(feedQueries[index]?.data ?? null),
    }));
  }, [analyzed, feedQueries]);

  const attentionPatients = useMemo<CohortAttentionPatient[]>(() => {
    const withFlags = readingSets
      .map((set, index) => {
        const patient = analyzed[index];
        if (!patient) return null;
        const flags = deriveAttentionFlags(set, 14);
        if (flags.length === 0) return null;
        const windowed = filterReadingsInWindow(set.readings, 14);
        const last = windowed[windowed.length - 1] ?? null;
        return {
          patient,
          flags,
          lastReadingValue: last?.value_mg_dl ?? null,
          lastReadingAt: last?.taken_at ?? null,
        };
      })
      .filter((x): x is CohortAttentionPatient => x !== null);
    withFlags.sort((a, b) => {
      const weight = (flag: AttentionFlag) => (flag.severity === "needs_review" ? 0 : 1);
      const rankA = a.flags.reduce((min, f) => Math.min(min, weight(f)), 0);
      const rankB = b.flags.reduce((min, f) => Math.min(min, weight(f)), 0);
      return rankA - rankB;
    });
    return withFlags;
  }, [readingSets, analyzed]);

  const cohortByPeriod = useMemo(() => {
    return {
      "7d": aggregateCohortMetrics(readingSets, COHORT_PERIOD_DAYS["7d"]),
      "30d": aggregateCohortMetrics(readingSets, COHORT_PERIOD_DAYS["30d"]),
      "90d": aggregateCohortMetrics(readingSets, COHORT_PERIOD_DAYS["90d"]),
    };
  }, [readingSets]);

  const statusByPeriod = useMemo(() => {
    return {
      "7d": computeStatusDistribution(readingSets, COHORT_PERIOD_DAYS["7d"]),
      "30d": computeStatusDistribution(readingSets, COHORT_PERIOD_DAYS["30d"]),
      "90d": computeStatusDistribution(readingSets, COHORT_PERIOD_DAYS["90d"]),
    };
  }, [readingSets]);

  const monitoring30d = useMemo(
    () => computeMonitoringDistribution(readingSets, COHORT_PERIOD_DAYS["30d"]),
    [readingSets]
  );

  const trendsByPeriod = useMemo(() => {
    return {
      "7d": compareCohortTrends(readingSets, COHORT_PERIOD_DAYS["7d"]),
      "30d": compareCohortTrends(readingSets, COHORT_PERIOD_DAYS["30d"]),
      "90d": compareCohortTrends(readingSets, COHORT_PERIOD_DAYS["90d"]),
    };
  }, [readingSets]);

  const meanByWindow = useMemo(
    () => ({
      "7d": cohortPeriodMeanMgDl(readingSets, COHORT_PERIOD_DAYS["7d"]),
      "30d": cohortPeriodMeanMgDl(readingSets, COHORT_PERIOD_DAYS["30d"]),
      "90d": cohortPeriodMeanMgDl(readingSets, COHORT_PERIOD_DAYS["90d"]),
    }),
    [readingSets]
  );

  const previousMeanByWindow = useMemo(() => {
    const previous: Record<CohortPeriodKey, number | null> = {
      "7d": null,
      "30d": null,
      "90d": null,
    };
    for (const key of Object.keys(COHORT_PERIOD_DAYS) as CohortPeriodKey[]) {
      const days = COHORT_PERIOD_DAYS[key];
      previous[key] = cohortPreviousPeriodMeanMgDl(
        readingSets.flatMap((s) => s.readings),
        days
      );
    }
    return previous;
  }, [readingSets]);

  const dailySeriesByWindow = useMemo(() => {
    const series = (days: number): TrendDayPoint[] =>
      buildDailyMeanSeries(readingSets, days).map((p) => ({
        label: new Date(p.dayStart).toISOString().slice(5, 10),
        value: p.value,
      }));
    return {
      "7d": series(COHORT_PERIOD_DAYS["7d"]),
      "30d": series(COHORT_PERIOD_DAYS["30d"]),
      "90d": series(COHORT_PERIOD_DAYS["90d"]),
    };
  }, [readingSets]);

  const careGaps = useMemo(() => groupCareGapTasks(tasks.tasks), [tasks.tasks]);

  const isLoadingFeed = feedQueries.some((q) => q.isLoading);
  const hasFeedErrors = feedQueries.some((q) => q.isError);
  const failedPatients = feedQueries.filter((q) => q.isError).length;
  const hasFeedQueriesSettled = analyzed.length > 0 && feedQueries.every((q) => !q.isPending);
  const latestFeedUpdateAt = useMemo(
    () => feedQueries.reduce<number | null>((latest, q) => {
      const t = q.dataUpdatedAt ?? 0;
      return latest === null || t > latest ? (t > 0 ? t : latest) : latest;
    }, null),
    [feedQueries]
  );

  return {
    analyzedCount: analyzed.length,
    totalPatients: patients.length,
    isLoadingFeed,
    hasFeedErrors,
    failedPatients,
    hasFeedQueriesSettled,
    latestFeedUpdateAt,
    refreshCohort: async () => {
      await Promise.all(feedQueries.map((q) => q.refetch()));
    },

    attentionPatients,

    cohortByPeriod,
    statusByPeriod,
    monitoring30d,
    trendsByPeriod,

    meanByWindow,
    previousMeanByWindow,
    dailySeriesByWindow,

    reviewTotal: review.artifactCount,
    reviewKinds: summarizeReviewQueue(review.queue),
    reviewQueue: review.queue,
    isReviewLoading: review.isLoading,

    careTaskTotal: tasks.taskCount,
    careGaps,
    isTasksLoading: tasks.isLoading,
  };
}

export type { CohortMetrics, CohortStatusBucket, MonitoringBucket, AttentionFlag };
export { classifyCohortStatus };