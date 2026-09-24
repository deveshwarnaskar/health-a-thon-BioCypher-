import { useQuery } from "@tanstack/react-query";
import { fetchPatientDetail } from "./api";
import { doctorKeys } from "./doctorKeys";
import type { PatientSummaryResponse } from "../../services/schemas/patients";

export type UsePatientDetailResult = {
  patient: PatientSummaryResponse | null;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  refetch: () => Promise<unknown>;
};

/**
 * One patient record (Gate 10F-B contract). Cross-facility / deactivated /
 * missing patients resolve to 404 (EntityNotFound) on the backend — the UI
 * must treat that as "unavailable" without revealing existence.
 */
export function usePatientDetail(
  patientId: string | null | undefined,
  options?: { enabled?: boolean }
): UsePatientDetailResult {
  const isEnabled = Boolean(patientId) && (options?.enabled ?? true);

  const query = useQuery({
    queryKey: patientId ? doctorKeys.patient(patientId) : ["doctor", "patients", "none"],
    queryFn: async () => {
      if (!patientId) throw new Error("patientId is required for patient detail");
      return fetchPatientDetail(patientId);
    },
    enabled: isEnabled,
    staleTime: 30_000,
    retry: 1,
  });

  return {
    patient: query.data ?? null,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  };
}