import { useQuery } from "@tanstack/react-query";
import { fetchCaregiverPatients } from "./api";
import type { CaregiverPatientListItem } from "../../services/schemas/caregiver";

/**
 * Query keys are intentionally scoped to the authenticated caregiver
 * (["caregivers", "me", "patients"]) and are never persisted: relationship
 * state is ephemeral server state refreshed on focus/entry.
 */
export const caregiverKeys = {
  all: ["caregivers"] as const,
  me: () => ["caregivers", "me"] as const,
  patients: () => ["caregivers", "me", "patients"] as const,
};

export type UseCaregiverPatientsResult = {
  patients: CaregiverPatientListItem[];
  patientCount: number;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  refetch: () => Promise<unknown>;
};

export function useCaregiverPatients(options?: {
  enabled?: boolean;
}): UseCaregiverPatientsResult {
  const query = useQuery({
    queryKey: caregiverKeys.patients(),
    queryFn: () => fetchCaregiverPatients(),
    enabled: options?.enabled ?? true,
    // Relationship discovery is tenant-scoped server state. 30s staleness
    // mirrors the app-wide query client; auth-expired 401s are routed to the
    // global signal by the shared query cache (no retry loop here).
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