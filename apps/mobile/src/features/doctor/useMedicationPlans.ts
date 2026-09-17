import { useQuery } from "@tanstack/react-query";
import { fetchMedicationPlans } from "./api";
import { doctorKeys } from "./doctorKeys";
import type { MedicationPlanResponse } from "../../services/schemas/medication";

export type UseMedicationPlansResult = {
  plans: MedicationPlanResponse[];
  planCount: number;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  refetch: () => Promise<unknown>;
};

/**
 * Clinician-authored medication plans (Gate 10F-B contract). The backend
 * endpoint is facility-scoped; when scoped to a patient the facility list is
 * fetched once and filtered client-side for display. Authorization stays on
 * the backend for every request.
 */
export function useMedicationPlans(
  patientId?: string | null,
  options?: { enabled?: boolean }
): UseMedicationPlansResult {
  const query = useQuery({
    queryKey: doctorKeys.medicationPlans(patientId ?? undefined),
    queryFn: async () => {
      const all = await fetchMedicationPlans();
      if (!patientId) {
        return all;
      }
      const items = all.items.filter((plan) => plan.patient_id === patientId);
      return { plan_count: items.length, items };
    },
    enabled: options?.enabled ?? true,
    staleTime: 30_000,
    retry: 1,
  });

  return {
    plans: query.data?.items ?? [],
    planCount: query.data?.plan_count ?? 0,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  };
}