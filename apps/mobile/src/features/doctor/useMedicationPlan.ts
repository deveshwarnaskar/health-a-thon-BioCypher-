import { useQuery } from "@tanstack/react-query";
import { fetchMedicationPlan } from "./api";
import { doctorKeys } from "./doctorKeys";
import type { MedicationPlanResponse } from "../../services/schemas/medication";

export type UseMedicationPlanResult = {
  plan: MedicationPlanResponse | null;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  refetch: () => Promise<unknown>;
};

/**
 * ONE clinician-authored medication plan (Gate 10F-B contract).
 * Cross-facility / cross-tenant / deactivated-patient / missing plans never
 * resolve on the backend; the UI treats failure as unavailable.
 */
export function useMedicationPlan(
  planId: string | null | undefined,
  options?: { enabled?: boolean }
): UseMedicationPlanResult {
  const isEnabled = Boolean(planId) && (options?.enabled ?? true);

  const query = useQuery({
    queryKey: planId ? doctorKeys.medicationPlan(planId) : ["doctor", "medication-plans", "none"],
    queryFn: async () => {
      if (!planId) throw new Error("planId is required for medication plan detail");
      return fetchMedicationPlan(planId);
    },
    enabled: isEnabled,
    staleTime: 30_000,
    retry: 1,
  });

  return {
    plan: query.data ?? null,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  };
}