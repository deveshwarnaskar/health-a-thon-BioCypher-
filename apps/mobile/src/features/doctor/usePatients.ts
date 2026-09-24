import { useQuery } from "@tanstack/react-query";
import { fetchPatients } from "./api";
import { doctorKeys } from "./doctorKeys";
import type { PatientSummaryResponse } from "../../services/schemas/patients";

export type UsePatientsResult = {
  patients: PatientSummaryResponse[];
  patientCount: number;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  refetch: () => Promise<unknown>;
};

/**
 * Facility-scoped clinician patient cohort (Gate 10F-B contract).
 * Selection stays ephemeral in React state — the backend re-authorizes every
 * patient-specific request.
 */
export function usePatients(options?: { enabled?: boolean }): UsePatientsResult {
  const query = useQuery({
    queryKey: doctorKeys.patients(),
    queryFn: () => fetchPatients(),
    enabled: options?.enabled ?? true,
    staleTime: 30_000,
    retry: 1,
  });

  return {
    patients: query.data?.items ?? [],
    patientCount: query.data?.patient_count ?? 0,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  };
}