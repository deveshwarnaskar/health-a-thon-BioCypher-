import { useQuery } from "@tanstack/react-query";
import { fetchClinicianMeals } from "./api";
import { mealKeys, type ClinicianMealObservation } from "./types";

export type UseClinicianMealsOptions = {
  enabled?: boolean;
};

export function useClinicianMeals(
  patientId: string | null | undefined,
  options?: UseClinicianMealsOptions
) {
  const isEnabled = Boolean(patientId) && (options?.enabled ?? true);

  const query = useQuery<ClinicianMealObservation[]>({
    queryKey: patientId ? mealKeys.clinicianFeed(patientId) : mealKeys.all,
    queryFn: async () => {
      if (!patientId) {
        return [];
      }
      return fetchClinicianMeals(patientId);
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
