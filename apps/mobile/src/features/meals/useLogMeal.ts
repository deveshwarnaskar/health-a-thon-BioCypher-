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
import { connectivityService } from "../../connectivity/connectivityService";
import { localDatabase } from "../../db/database";
import { localSessionIsolation } from "../../db/isolation";
import { OfflineCaptureService } from "../../sync/offlineCapture";
import { MealRepository } from "../../db/repositories";

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

      const idempotencyKey = idempotencyKeyFor(mutationKeyFor(capture), mealKeyStore);

      // Local offline capture path if network is offline
      if (!connectivityService.isOnline() && localDatabase.isOpen() && localSessionIsolation.hasContext()) {
        const offlineService = new OfflineCaptureService(localDatabase.getDb());
        const context = localSessionIsolation.getContext();
        return offlineService.captureMeal(
          context,
          {
            patient_id: patientId,
            description: data.description,
            portion: data.portion ?? null,
            recorded_at: capture.recordedAtIso,
          },
          idempotencyKey
        );
      }

      try {
        const result = await submitMealDraft(
          {
            patient_id: patientId,
            description: data.description,
            portion: data.portion ?? null,
            recorded_at: capture.recordedAtIso,
          },
          idempotencyKey
        );

        // Cache locally in SQLCipher
        if (localDatabase.isOpen() && localSessionIsolation.hasContext()) {
          const mealRepo = new MealRepository(localDatabase.getDb());
          const context = localSessionIsolation.getContext();
          await mealRepo
            .insert({
              localId: result.meal_observation_id,
              serverId: result.meal_observation_id,
              tenantId: context.tenantId,
              userId: context.userId,
              patientId,
              description: data.description,
              portionSize: data.portion?.food_key ?? null,
              portionCount: data.portion?.quantity ?? null,
              portionGrams: null,
              recordedAt: capture.recordedAtIso,
              syncStatus: "SYNCED",
              idempotencyKey,
              createdAt: capture.recordedAtIso,
              syncedAt: new Date().toISOString(),
            })
            .catch(() => {});
        }

        return result;
      } catch (err: any) {
        // Transparent offline fallback on network drop
        if (
          (err?.kind === "NETWORK_ERROR" || !err?.httpStatus) &&
          localDatabase.isOpen() &&
          localSessionIsolation.hasContext()
        ) {
          const offlineService = new OfflineCaptureService(localDatabase.getDb());
          const context = localSessionIsolation.getContext();
          return offlineService.captureMeal(
            context,
            {
              patient_id: patientId,
              description: data.description,
              portion: data.portion ?? null,
              recorded_at: capture.recordedAtIso,
            },
            idempotencyKey
          );
        }
        throw err;
      }
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
