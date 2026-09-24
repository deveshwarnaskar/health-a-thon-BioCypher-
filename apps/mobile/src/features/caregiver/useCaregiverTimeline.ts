import { useQuery } from "@tanstack/react-query";
import { fetchObservationFeed } from "../glucose/api";
import type {
  PatientGlucoseObservation,
  PatientMealObservation,
} from "../../services/schemas/clinical";

export type UnifiedTimelineItem =
  | (PatientGlucoseObservation & { sortTimestamp: number; formattedTime: string })
  | (PatientMealObservation & { sortTimestamp: number; formattedTime: string });

export type CaregiverTimelineSummary = {
  latestGlucose: PatientGlucoseObservation | null;
  latestGlucoseStatus: "in-range" | "low" | "high" | "unknown";
  todayReadingsCount: number;
  todayMealsCount: number;
  todayAvgGlucose: number | null;
};

export type UseCaregiverTimelineResult = {
  items: UnifiedTimelineItem[];
  glucoseReadings: PatientGlucoseObservation[];
  meals: PatientMealObservation[];
  summary: CaregiverTimelineSummary;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  refetch: () => Promise<unknown>;
};

function formatEventTime(isoString: string): string {
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return isoString;
    return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  } catch {
    return isoString;
  }
}

function isSameCalendarDay(d1: Date, d2: Date): boolean {
  return (
    d1.getFullYear() === d2.getFullYear() &&
    d1.getMonth() === d2.getMonth() &&
    d1.getDate() === d2.getDate()
  );
}

export function useCaregiverTimeline(
  patientId: string | null | undefined,
  options?: { enabled?: boolean; limit?: number }
): UseCaregiverTimelineResult {
  const isEnabled = Boolean(patientId) && (options?.enabled ?? true);

  const query = useQuery({
    queryKey: ["caregivers", "timeline", patientId ?? "none"],
    queryFn: async () => {
      if (!patientId) throw new Error("patientId is required for caregiver timeline");
      return fetchObservationFeed(patientId, options?.limit ?? 50);
    },
    enabled: isEnabled,
    staleTime: 10_000,
  });

  const rawItems = query.data?.items ?? [];
  const now = new Date();

  const glucoseReadings: PatientGlucoseObservation[] = [];
  const meals: PatientMealObservation[] = [];
  const unifiedItems: UnifiedTimelineItem[] = [];

  let todayGlucoseSum = 0;
  let todayGlucoseCount = 0;
  let todayMealsCount = 0;

  for (const item of rawItems) {
    if (item.kind === "glucose") {
      glucoseReadings.push(item);
      const timeMs = new Date(item.taken_at).getTime();
      const sortTimestamp = isNaN(timeMs) ? 0 : timeMs;
      unifiedItems.push({
        ...item,
        sortTimestamp,
        formattedTime: formatEventTime(item.taken_at),
      });

      if (!isNaN(timeMs) && isSameCalendarDay(new Date(timeMs), now)) {
        if (typeof item.value_mg_dl === "number") {
          todayGlucoseSum += item.value_mg_dl;
          todayGlucoseCount++;
        }
      }
    } else if (item.kind === "meal") {
      meals.push(item);
      const timeMs = new Date(item.recorded_at).getTime();
      const sortTimestamp = isNaN(timeMs) ? 0 : timeMs;
      unifiedItems.push({
        ...item,
        sortTimestamp,
        formattedTime: formatEventTime(item.recorded_at),
      });

      if (!isNaN(timeMs) && isSameCalendarDay(new Date(timeMs), now)) {
        todayMealsCount++;
      }
    }
  }

  // Sort descending: most recent observations first
  unifiedItems.sort((a, b) => b.sortTimestamp - a.sortTimestamp);

  const latestGlucose = glucoseReadings.length > 0 ? glucoseReadings[0] : null;
  let latestGlucoseStatus: "in-range" | "low" | "high" | "unknown" = "unknown";
  if (latestGlucose && typeof latestGlucose.value_mg_dl === "number") {
    if (latestGlucose.value_mg_dl < 70) {
      latestGlucoseStatus = "low";
    } else if (latestGlucose.value_mg_dl > 180) {
      latestGlucoseStatus = "high";
    } else {
      latestGlucoseStatus = "in-range";
    }
  }

  const todayAvgGlucose =
    todayGlucoseCount > 0 ? Math.round(todayGlucoseSum / todayGlucoseCount) : null;

  return {
    items: unifiedItems,
    glucoseReadings,
    meals,
    summary: {
      latestGlucose: latestGlucose ?? null,
      latestGlucoseStatus,

      todayReadingsCount: todayGlucoseCount,
      todayMealsCount,
      todayAvgGlucose,
    },
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  };
}
