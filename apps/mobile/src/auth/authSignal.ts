import type { ApiErrorDetails } from "../services/api/errors";

export type AuthExpiredListener = (error: ApiErrorDetails) => void;

/**
 * Observable "auth-expired" signal raised by the API client on every 401 so
 * that Gate 10C's AuthSessionProvider can trigger one session wipe/redirect
 * regardless of which request observed the expiry. No refresh is faked here.
 */
export type AuthExpiredSignal = {
  subscribe(listener: AuthExpiredListener): () => void;
  emit(error: ApiErrorDetails): void;
};

export function createAuthExpiredSignal(): AuthExpiredSignal {
  const listeners = new Set<AuthExpiredListener>();

  return {
    subscribe(listener) {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    emit(error) {
      for (const listener of [...listeners]) {
        listener(error);
      }
    },
  };
}