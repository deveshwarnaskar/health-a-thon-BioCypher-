import { useQuery } from "@tanstack/react-query";
import { fetchClinicalInsights, type ClinicalInsightsResponse } from "./api";
import { doctorKeys } from "./doctorKeys";

export function useClinicalInsights(patientId: string, options?: { enabled?: boolean }) {
  const query = useQuery<ClinicalInsightsResponse>({
    queryKey: doctorKeys.insights(patientId),
    queryFn: () => fetchClinicalInsights(patientId),
    enabled: Boolean(patientId) && (options?.enabled ?? true),
    staleTime: 60_000,
  });

  return {
    insights: query.data,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  };
}
