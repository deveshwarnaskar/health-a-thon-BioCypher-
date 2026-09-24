import { useQuery } from "@tanstack/react-query";
import { fetchPatientClinicalState, type PatientClinicalState } from "./api";
import { doctorKeys } from "./doctorKeys";

export function usePatientClinicalState(
  patientId: string,
  windowDays: number = 14,
  options?: { enabled?: boolean }
) {
  const query = useQuery<PatientClinicalState>({
    queryKey: doctorKeys.clinicalState(patientId, windowDays),
    queryFn: () => fetchPatientClinicalState(patientId, windowDays),
    enabled: Boolean(patientId) && (options?.enabled ?? true),
    staleTime: 60_000,
  });

  return {
    state: query.data,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  };
}
