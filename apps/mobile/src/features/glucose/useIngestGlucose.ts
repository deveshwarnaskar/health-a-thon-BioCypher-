import { useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { submitGlucoseReading } from "./api";
import { glucoseKeys, type ReadingTag } from "./types";
import { secureUuid } from "../../services/api/correlation";
import {
  idempotencyKeyFor,
  InMemoryIdempotencyKeyStore,
} from "../../services/api/idempotency";
import type { IngestGlucoseResponse } from "../../services/schemas/clinical";

/**
 * Glucose ingestion mutation with Gate 09 idempotency (see also
 * backend/interfaces/http/ops/idempotency.py).
 *
 * A "capture session" is the immutable logical intent of ONE reading:
 *
 * - ``id``         — unique draft identity. Retries of the SAME session always
 *                    resolve to the SAME Idempotency-Key.
 * - ``takenAtIso`` — fixed when the session is created and reused verbatim on
 *                    every retry. Gate 09 fingerprints an HMAC over the RAW
 *                    body (method|path|body), so a retry after a network drop
 *                    MUST carry byte-identical JSON or the backend rejects it
 *                    with 409 IDEMPOTENCY_KEY_MISMATCH. A live "now" computed
 *                    per attempt would defeat deduplication.
 *
 * The key is released and the session discarded on SUCCESS (a genuinely new
 * capture allocates a fresh key); on ERROR the session is preserved so any
 * immediate retry reuses the same key and byte-identical body.
 */
export type IngestGlucoseData = {
  value_mg_dl: number;
  tag?: ReadingTag | null;
};

export type UseIngestGlucoseOptions = {
  patientId: string | null | undefined;
  onSuccess?: (data: IngestGlucoseResponse) => void;
  onError?: (error: unknown) => void;
};

type CaptureSession = {
  readonly id: string;
  readonly takenAtIso: string;
};

function createCaptureSession(): CaptureSession {
  return { id: secureUuid(), takenAtIso: new Date().toISOString() };
}

const glucoseKeyStore = new InMemoryIdempotencyKeyStore();
const mutationKeyFor = (session: CaptureSession): string => `glucose:capture:${session.id}`;

export function useIngestGlucose({
  patientId,
  onSuccess,
  onError,
}: UseIngestGlucoseOptions) {
  const queryClient = useQueryClient();
  const sessionRef = useRef<CaptureSession | null>(null);
  const [session, setSession] = useState<CaptureSession | null>(null);

  const mutation = useMutation({
    mutationFn: async (data: IngestGlucoseData): Promise<IngestGlucoseResponse> => {
      if (!patientId) {
        throw new Error("Cannot submit reading: patient profile is not linked.");
      }

      const capture = sessionRef.current ?? createCaptureSession();
      sessionRef.current = capture;
      setSession(capture);

      return submitGlucoseReading(
        {
          patient_id: patientId,
          value_mg_dl: data.value_mg_dl,
          tag: data.tag ?? null,
          taken_at: capture.takenAtIso,
        },
        idempotencyKeyFor(mutationKeyFor(capture), glucoseKeyStore)
      );
    },
    onSuccess: (data) => {
      if (sessionRef.current) {
        glucoseKeyStore.remove(mutationKeyFor(sessionRef.current));
      }
      sessionRef.current = null;
      setSession(null);
      if (patientId) {
        void queryClient.invalidateQueries({ queryKey: glucoseKeys.feed(patientId) });
      }
      onSuccess?.(data);
    },
    onError: (error) => {
      // Session is intentionally PRESERVED here so a retry reuses the same
      // Idempotency-Key and byte-identical body (Gate 09 semantics).
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
    reset: mutation.reset,
    /** Reading time locked for the current draft (display-only). */
    takenAtIso: session?.takenAtIso ?? null,
  };
}