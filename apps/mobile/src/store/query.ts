import { QueryClient, QueryCache } from "@tanstack/react-query";
import type { ApiErrorDetails } from "../services/api/errors";
import { isAuthExpiredSignal } from "../services/api/errors";
import { globalAuthExpiredSignal } from "../auth/globalAuthSignal";

export type QueryClientOptions = {
  /** Additional listener invoked when a 401 auth-expired event fires. */
  onAuthExpired?: (error: ApiErrorDetails) => void;
  /** Backend never re-checks identity more often than this for real queries. */
  staleTimeMs?: number;
  retry?: number;
};

/**
 * TanStack Query foundation (Gate 10A §10 tier 1). Server entities live here:
 * observations, plans, artifact listings, patient profiles. Central error
 * handling routes 401s to the global auth-expired signal so the session manager
 * can invalidate the session and navigate to login.
 */
export function createQueryClient(options: QueryClientOptions = {}): QueryClient {
  const queryCache = new QueryCache({
    onError: (error) => {
      const details = error as unknown as ApiErrorDetails;
      if (isAuthExpiredSignal(details)) {
        globalAuthExpiredSignal.emit(details);
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