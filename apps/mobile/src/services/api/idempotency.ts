import { secureUuid } from "./correlation";

/**
 * Idempotency-Key lifecycle (Gate 09 contract + Gate 10A §9):
 *
 * - One key per LOGICAL mutation. The key is generated on first attempt and
 *   MUST be reused verbatim on any retry of that same mutation, so the backend
 *   deduplicates replay (INSERT ... ON CONFLICT DO NOTHING + RETURNING).
 * - A NEW logical mutation (different user intent, e.g. a fresh capture after
 *   the failed one was abandoned) MUST regenerate the key.
 *
 * The key store is in-memory for the foundation. Persistence across app
 * restarts lands with the offline outbox (Expo SQLite/SQLCipher/Drizzle, a
 * later gate).
 */

export interface IdempotencyKeyStore {
  get(mutationKey: string): string | undefined;
  set(mutationKey: string, key: string): void;
  remove(mutationKey: string): void;
  clear(): void;
}

export class InMemoryIdempotencyKeyStore implements IdempotencyKeyStore {
  private keys = new Map<string, string>();

  get(mutationKey: string): string | undefined {
    return this.keys.get(mutationKey);
  }

  set(mutationKey: string, key: string): void {
    this.keys.set(mutationKey, key);
  }

  remove(mutationKey: string): void {
    this.keys.delete(mutationKey);
  }

  clear(): void {
    this.keys.clear();
  }
}

/**
 * Composite identifier for a logical mutation. Callers must include enough
 * identity (e.g. patient_id + captured_at + local draft id) that retries of
 * the same intent produce the same key while distinct intents differ.
 */
export type MutationKey = string;

export function idempotencyKeyFor(
  mutationKey: MutationKey,
  store: IdempotencyKeyStore,
  nowGenerator: () => string = secureUuid,
): string {
  const existing = store.get(mutationKey);
  if (existing) {
    return existing;
  }
  const next = nowGenerator();
  store.set(mutationKey, next);
  return next;
}

/** New logical mutation: allocate a fresh key (removes any prior one). */
export function freshIdempotencyKey(
  mutationKey: MutationKey,
  store: IdempotencyKeyStore,
  nowGenerator: () => string = secureUuid,
): string {
  const next = nowGenerator();
  store.set(mutationKey, next);
  return next;
}