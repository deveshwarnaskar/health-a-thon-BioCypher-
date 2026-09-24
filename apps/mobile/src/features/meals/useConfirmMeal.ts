import { useMutation, useQueryClient } from "@tanstack/react-query";
import { submitMealConfirmation } from "./api";
import { mealKeys } from "./types";
import {
  idempotencyKeyFor,
  InMemoryIdempotencyKeyStore,
} from "../../services/api/idempotency";
import type {
  ConfirmMealRequest,
  ConfirmMealResponse,
} from "../../services/schemas/meals";

export type ConfirmMealData = {
  mealObservationId: string;
  patientId?: string | null;
  corrected_description?: string | null;
  corrected_portion?: ConfirmMealRequest["corrected_portion"];
};

export type UseConfirmMealOptions = {
  onSuccess?: (data: ConfirmMealResponse) => void;
  onError?: (error: unknown) => void;
};

const confirmMealKeyStore = new InMemoryIdempotencyKeyStore();

export function useConfirmMeal(options?: UseConfirmMealOptions) {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: async (data: ConfirmMealData): Promise<ConfirmMealResponse> => {
      const mutationKey = `meal:confirm:${data.mealObservationId}`;
      const idempotencyKey = idempotencyKeyFor(mutationKey, confirmMealKeyStore);

      const request: ConfirmMealRequest = {};
      if (data.corrected_description !== undefined) {
        request.corrected_description = data.corrected_description;
      }
      if (data.corrected_portion !== undefined) {
        request.corrected_portion = data.corrected_portion;
      }

      return submitMealConfirmation(
        data.mealObservationId,
        request,
        idempotencyKey
      );
    },
    onSuccess: (data, variables) => {
      confirmMealKeyStore.remove(`meal:confirm:${variables.mealObservationId}`);
      if (variables.patientId) {
        void queryClient.invalidateQueries({ queryKey: mealKeys.feed(variables.patientId) });
      }
      void queryClient.invalidateQueries({ queryKey: mealKeys.all });
      options?.onSuccess?.(data);
    },
    onError: (error) => {
      options?.onError?.(error);
    },
  });

  return {
    mutate: mutation.mutate,
    mutateAsync: mutation.mutateAsync,
    isPending: mutation.isPending,
    isSuccess: mutation.isSuccess,
    isError: mutation.isError,
    error: mutation.error,
    reset: mutation.reset,
  };
}
