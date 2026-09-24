import { useQuery } from "@tanstack/react-query";
import { fetchPatientMeals } from "./api";
import { mealKeys, type PatientMealObservation } from "./types";

export type UsePatientMealsOptions = {
  enabled?: boolean;
};

export function usePatientMeals(
  patientId: string | null | undefined,
  options?: UsePatientMealsOptions
) {
  const isEnabled = Boolean(patientId) && (options?.enabled ?? true);

  const query = useQuery<PatientMealObservation[]>({
    queryKey: patientId ? mealKeys.feed(patientId) : mealKeys.all,
    queryFn: async () => {
      if (!patientId) {
        return [];
      }
      return fetchPatientMeals(patientId);
    },
    enabled: isEnabled,
  });

  return {
    meals: query.data ?? [],
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  };
}
