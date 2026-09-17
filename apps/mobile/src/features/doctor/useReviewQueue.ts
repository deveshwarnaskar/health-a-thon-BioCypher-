import { useQuery } from "@tanstack/react-query";
import { fetchReviewQueue } from "./api";
import { doctorKeys } from "./doctorKeys";
import type { AIArtifactResponse } from "../../services/schemas/ai";

export type UseReviewQueueResult = {
  queue: AIArtifactResponse[];
  artifactCount: number;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  refetch: () => Promise<unknown>;
};

/**
 * Clinician pending-review queue (Gate 10F-B contract → Gate 10F-M).
 * The backend returns ONLY PENDING_REVIEW artifacts, facility-scoped, in
 * deterministic order; the client displays that order verbatim and adds none.
 */
export function useReviewQueue(options?: { enabled?: boolean }): UseReviewQueueResult {
  const query = useQuery({
    queryKey: doctorKeys.reviewQueue(),
    queryFn: () => fetchReviewQueue(),
    enabled: options?.enabled ?? true,
    staleTime: 30_000,
    retry: 1,
  });

  return {
    queue: query.data?.items ?? [],
    artifactCount: query.data?.artifact_count ?? 0,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  };
}