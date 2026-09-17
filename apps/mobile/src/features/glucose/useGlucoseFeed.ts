import { useQuery } from "@tanstack/react-query";
import { fetchObservationFeed } from "./api";
import { glucoseKeys } from "./types";
import type { PatientGlucoseObservation } from "../../services/schemas/clinical";

export type UseGlucoseFeedResult = {
  readings: PatientGlucoseObservation[];
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  refetch: () => Promise<unknown>;
};

export function useGlucoseFeed(
  patientId: string | null | undefined,
  options?: { enabled?: boolean; limit?: number }
): UseGlucoseFeedResult {
  const isEnabled = Boolean(patientId) && (options?.enabled ?? true);

  const query = useQuery({
    queryKey: patientId ? glucoseKeys.feed(patientId) : ["clinical", "observations", "none"],
    queryFn: async () => {
      if (!patientId) throw new Error("patientId is required for observation feed");
      return fetchObservationFeed(patientId, options?.limit ?? 50);
    },
    enabled: isEnabled,
  });

  const allItems = query.data?.items ?? [];
  const readings = allItems.filter(
    (item): item is PatientGlucoseObservation => item.kind === "glucose"
  );

  return {
    readings,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  };
}
