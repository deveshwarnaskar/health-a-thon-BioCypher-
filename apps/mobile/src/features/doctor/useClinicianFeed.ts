import { useQuery } from "@tanstack/react-query";
import { fetchClinicianFeed } from "./api";
import { doctorKeys } from "./doctorKeys";
import type { ClinicianObservationFeedResponse } from "../../services/schemas/clinical";

export type UseClinicianFeedResult = {
  feed: ClinicianObservationFeedResponse | null;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  refetch: () => Promise<unknown>;
};

/**
 * Clinician-only observation feed for ONE scoped patient (Gate 10F-B contract
 * → Gate 10F-M). Requires the backend coarse READ_OBSERVATIONS grant; the
 * response is validated against the clinician schema and the defense-in-depth
 * guard (assertClinicianSafeFeed). Patient/caregiver screens NEVER mount this
 * hook — they use the separate patient feed pipeline.
 */
export function useClinicianFeed(
  patientId: string | null | undefined,
  options?: { enabled?: boolean }
): UseClinicianFeedResult {
  const isEnabled = Boolean(patientId) && (options?.enabled ?? true);

  const query = useQuery({
    queryKey: patientId
      ? doctorKeys.clinicianObservations(patientId)
      : ["doctor", "observations", "none"],
    queryFn: async () => {
      if (!patientId) throw new Error("patientId is required for clinician feed");
      return fetchClinicianFeed(patientId);
    },
    enabled: isEnabled,
    staleTime: 30_000,
    retry: 1,
  });

  return {
    feed: query.data ?? null,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  };
}