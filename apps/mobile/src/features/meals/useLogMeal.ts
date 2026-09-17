import { useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { submitMealDraft } from "./api";
import { mealKeys } from "./types";
import { secureUuid } from "../../services/api/correlation";
import {
  idempotencyKeyFor,
  InMemoryIdempotencyKeyStore,
} from "../../services/api/idempotency";
import type {
  LogMealResponse,
  MealPortionRequest,
} from "../../services/schemas/meals";

export type LogMealData = {
  description: string;
  portion?: MealPortionRequest | null;
};

export type UseLogMealOptions = {
  patientId: string | null | undefined;
  onSuccess?: (data: LogMealResponse) => void;
  onError?: (error: unknown) => void;
};

type CaptureSession = {
  readonly id: string;
  readonly recordedAtIso: string;
};

function createCaptureSession(): CaptureSession {
  return { id: secureUuid(), recordedAtIso: new Date().toISOString() };
}

const mealKeyStore = new InMemoryIdempotencyKeyStore();
const mutationKeyFor = (session: CaptureSession): string => `meal:draft:${session.id}`;

export function useLogMeal({
  patientId,
  onSuccess,
  onError,
}: UseLogMealOptions) {
  const queryClient = useQueryClient();
  const sessionRef = useRef<CaptureSession | null>(null);
  const [session, setSession] = useState<CaptureSession | null>(null);

  const mutation = useMutation({
    mutationFn: async (data: LogMealData): Promise<LogMealResponse> => {
      if (!patientId) {
        throw new Error("Cannot submit meal: patient profile is not linked.");
      }

      const capture = sessionRef.current ?? createCaptureSession();
      sessionRef.current = capture;
      setSession(capture);

      return submitMealDraft(
        {
          patient_id: patientId,
          description: data.description,
          portion: data.portion ?? null,
          recorded_at: capture.recordedAtIso,
        },
        idempotencyKeyFor(mutationKeyFor(capture), mealKeyStore)
      );
    },
    onSuccess: (data) => {
      if (sessionRef.current) {
        mealKeyStore.remove(mutationKeyFor(sessionRef.current));
      }
      sessionRef.current = null;
      setSession(null);
      if (patientId) {
        void queryClient.invalidateQueries({ queryKey: mealKeys.feed(patientId) });
      }
      void queryClient.invalidateQueries({ queryKey: mealKeys.all });
      onSuccess?.(data);
    },
    onError: (error) => {
      // Session is intentionally preserved so any retry reuses the same
      // Idempotency-Key and byte-identical payload (Gate 09 semantics).
      onError?.(error);
    },
  });

  return {
    mutate: mutation.mutate,
    mutateAsync: mutation.mutateAsync,
    isPending: mutation.isPending,
    isSuccess: mutation.isSuccess,
    isError: mutation.isError,
    error: mutation.error,
    reset: () => {
      if (sessionRef.current) {
        mealKeyStore.remove(mutationKeyFor(sessionRef.current));
      }
      sessionRef.current = null;
      setSession(null);
      mutation.reset();
    },
    recordedAtIso: session?.recordedAtIso ?? null,
  };
}
