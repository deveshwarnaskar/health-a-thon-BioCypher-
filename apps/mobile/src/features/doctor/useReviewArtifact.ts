import { useRef } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { submitArtifactReview } from "./api";
import { doctorKeys } from "./doctorKeys";
import { secureUuid } from "../../services/api/correlation";
import {
  idempotencyKeyFor,
  InMemoryIdempotencyKeyStore,
} from "../../services/api/idempotency";
import type {
  ReviewAIArtifactRequest,
  ReviewAIArtifactResponse,
} from "../../services/schemas/ai";

/**
 * AI artifact review mutation with Gate 09 idempotency (see also
 * backend/interfaces/http/ops/idempotency.py).
 *
 * A "review session" is the immutable logical intent of ONE review of ONE
 * artifact:
 *
 * - a fresh session id is minted per review intent and kept in a ref so a
 *   retry (network drop, or the client's single 401-refresh retry) always
 *   resolves to the SAME Idempotency-Key and byte-identical body;
 * - the key is released and the session discarded on SUCCESS (a genuinely new
 *   review allocates a new key);
 * - on ERROR the session is preserved so any immediate retry reuses the same
 *   key — never a new key mid-retry.
 *
 * The client NEVER transitions the artifact state locally: only the backend
 * confirmation (response body / onSuccess) is treated as success.
 */
export type UseReviewArtifactOptions = {
  artifactId: string | null | undefined;
  onSuccess?: (data: ReviewAIArtifactResponse) => void;
  onError?: (error: unknown) => void;
};

type ReviewSession = {
  readonly id: string;
};

const reviewKeyStore = new InMemoryIdempotencyKeyStore();
const mutationKeyFor = (session: ReviewSession, artifactId: string): string =>
  `ai:review:${artifactId}:${session.id}`;

export function useReviewArtifact({ artifactId, onSuccess, onError }: UseReviewArtifactOptions) {
  const queryClient = useQueryClient();
  const sessionRef = useRef<ReviewSession | null>(null);

  const mutation = useMutation({
    mutationFn: async (request: ReviewAIArtifactRequest): Promise<ReviewAIArtifactResponse> => {
      if (!artifactId) {
        throw new Error("Cannot review artifact: no artifact selected.");
      }
      const session = sessionRef.current ?? { id: secureUuid() };
      sessionRef.current = session;
      const MutationKey = mutationKeyFor(session, artifactId);
      return submitArtifactReview(artifactId, request, idempotencyKeyFor(MutationKey, reviewKeyStore));
    },
    onSuccess: (data) => {
      if (sessionRef.current && artifactId) {
        reviewKeyStore.remove(mutationKeyFor(sessionRef.current, artifactId));
      }
      sessionRef.current = null;
      if (artifactId) {
        void queryClient.invalidateQueries({ queryKey: doctorKeys.reviewQueue() });
        void queryClient.invalidateQueries({ queryKey: doctorKeys.artifact(artifactId) });
      }
      onSuccess?.(data);
    },
    onError: (error) => {
      // Session is intentionally PRESERVED: a retry reuses the same
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