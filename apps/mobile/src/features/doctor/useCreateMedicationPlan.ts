import { useRef } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { connectivityService } from "../../connectivity/connectivityService";
import { createMedicationPlan } from "./api";
import { doctorKeys } from "./doctorKeys";
import { secureUuid } from "../../services/api/correlation";
import {
  idempotencyKeyFor,
  InMemoryIdempotencyKeyStore,
} from "../../services/api/idempotency";
import type { CreateMedicationPlanRequest, CreateMedicationPlanResponse } from "../../services/schemas/medication";

/**
 * Medication-plan creation mutation with Gate 09 idempotency.
 *
 * CLINICIAN-AUTHORED ONLY: the request body carries patient_id / medication /
 * instruction and NEVER a prescriber, actor_id, tenant_id, or facility_id —
 * the backend derives the prescriber from the authenticated context.
 *
 * Same capture-session semantics as every other logical mutation: one key per
 * plan-creation intent, reused verbatim across retries and the client's single
 * 401-refresh retry; released on success, preserved on error.
 */
export type UseCreateMedicationPlanOptions = {
  onSuccess?: (data: CreateMedicationPlanResponse) => void;
  onError?: (error: unknown) => void;
};

type PlanSession = {
  readonly id: string;
};

const planKeyStore = new InMemoryIdempotencyKeyStore();
const mutationKeyFor = (session: PlanSession, patientId: string): string =>
  `medication:plan:${patientId}:${session.id}`;

export function useCreateMedicationPlan({
  onSuccess,
  onError,
}: UseCreateMedicationPlanOptions) {
  const queryClient = useQueryClient();
  const sessionRef = useRef<PlanSession | null>(null);

  const mutation = useMutation({
    mutationFn: async (
      request: CreateMedicationPlanRequest
    ): Promise<CreateMedicationPlanResponse> => {
      if (!connectivityService.isOnline()) {
        throw new Error("Medication plans can only be authored online by clinicians.");
      }
      const session = sessionRef.current ?? { id: secureUuid() };
      sessionRef.current = session;
      const MutationKey = mutationKeyFor(session, request.patient_id);
      return createMedicationPlan(request, idempotencyKeyFor(MutationKey, planKeyStore));
    },
    onSuccess: (data) => {
      if (sessionRef.current) {
        planKeyStore.remove(mutationKeyFor(sessionRef.current, data.patient_id));
      }
      sessionRef.current = null;
      // Invalidate the facility list AND the patient-scoped list views.
      void queryClient.invalidateQueries({ queryKey: doctorKeys.medicationPlans() });
      void queryClient.invalidateQueries({
        queryKey: doctorKeys.medicationPlans(data.patient_id),
      });
      onSuccess?.(data);
    },
    onError: (error) => {
      // Session is deliberately PRESERVED: a retry must reuse the same
      // Idempotency-Key and byte-identical body (Gate 09 semantics).
      onError?.(error);
    },
  });

  return {
    mutate: mutation.mutate,
    mutateAsync: mutation.mutateAsync,
    isPending: mutation.isPending,
    isError: mutation.isError,
    error: mutation.error,
    reset: mutation.reset,
  };
}