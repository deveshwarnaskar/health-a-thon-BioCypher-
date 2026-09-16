import { QueryClient, QueryCache } from "@tanstack/react-query";
import type { ApiErrorDetails } from "../services/api/errors";
import { isAuthExpiredSignal } from "../services/api/errors";

export type QueryClientOptions = {
  /** Invoked once when any request is rejected with a 401 auth-expired signal. */
  onAuthExpired?: (error: ApiErrorDetails) => void;
  /** Backend never re-checks identity more often than this for real queries. */
  staleTimeMs?: number;
  retry?: number;
};

/**
 * TanStack Query foundation (Gate 10A §10 tier 1). Server entities live here:
 * observations, plans, artifact listings, patient profiles. Central error
 * handling routes 401s to the auth-expired signal without scattering
 * per-screen handling.
 */
export function createQueryClient(options: QueryClientOptions = {}): QueryClient {
  const queryCache = new QueryCache({
    onError: (error) => {
      const details = error as unknown as ApiErrorDetails;
      if (isAuthExpiredSignal(details)) {
        options.onAuthExpired?.(details);
      }
    },
  });

  return new QueryClient({
    queryCache,
    defaultOptions: {
      queries: {
        staleTime: options.staleTimeMs ?? 30_000,
        gcTime: 5 * 60_000,
        retry: options.retry ?? 1,
        refetchOnWindowFocus: false,
        refetchOnReconnect: true,
      },
      mutations: {
        retry: 0,
      },
    },
  });
}

/** Shared app-wide query client (screens inject it via QueryClientProvider). */
export const queryClient = createQueryClient();