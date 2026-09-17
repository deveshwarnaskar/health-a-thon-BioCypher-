import { useQuery } from "@tanstack/react-query";
import { fetchArtifactDetail } from "./api";
import { doctorKeys } from "./doctorKeys";
import type { AIArtifactResponse } from "../../services/schemas/ai";

export type UseArtifactDetailResult = {
  artifact: AIArtifactResponse | null;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  refetch: () => Promise<unknown>;
};

/**
 * One AI review artifact (Gate 10F-B contract). The sealed detail contract
 * returns no payload/evidence body — only author-boundary + review facts.
 */
export function useArtifactDetail(
  artifactId: string | null | undefined,
  options?: { enabled?: boolean }
): UseArtifactDetailResult {
  const isEnabled = Boolean(artifactId) && (options?.enabled ?? true);

  const query = useQuery({
    queryKey: artifactId ? doctorKeys.artifact(artifactId) : ["doctor", "review", "artifact", "none"],
    queryFn: async () => {
      if (!artifactId) throw new Error("artifactId is required for artifact detail");
      return fetchArtifactDetail(artifactId);
    },
    enabled: isEnabled,
    staleTime: 30_000,
    retry: 1,
  });

  return {
    artifact: query.data ?? null,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  };
}