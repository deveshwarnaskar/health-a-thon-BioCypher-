import { describe, expect, it } from "vitest";
import {
  freshIdempotencyKey,
  idempotencyKeyFor,
  InMemoryIdempotencyKeyStore,
} from "../../src/services/api/idempotency";
import { isUuidV4 } from "../../src/services/api/correlation";

const SEQ = (() => {
  let n = 0;
  return () => `10000000-0000-4000-8000-${String(++n).padStart(12, "0")}`;
})();

describe("idempotency key lifecycle (Gate 09 contract)", () => {
  it("generates a fresh UUIDv4 key for a new logical mutation", () => {
    const store = new InMemoryIdempotencyKeyStore();
    const key = idempotencyKeyFor("obs:capture:p1:2026-09-16T10:00Z", store, SEQ);
    expect(isUuidV4(key)).toBe(true);
  });

  it("REUSES the same key verbatim when the same mutation is retried", () => {
    const store = new InMemoryIdempotencyKeyStore();
    const mutation = "obs:capture:p1:T12:00Z";
    const first = idempotencyKeyFor(mutation, store, SEQ);
    const retried = idempotencyKeyFor(mutation, store, SEQ);
    expect(retried).toBe(first);
  });

  it("never reuses a key across distinct logical mutations", () => {
    const store = new InMemoryIdempotencyKeyStore();
    const keyA = idempotencyKeyFor("obs:capture:p1:morning", store, SEQ);
    const keyB = idempotencyKeyFor("obs:capture:p1:evening", store, SEQ);
    expect(keyB).not.toBe(keyA);
  });

  it("regenerates the key for a NEW logical mutation on intent change", () => {
    const store = new InMemoryIdempotencyKeyStore();
    const mutation = "obs:capture:p1:10:00";
    const abandoned = idempotencyKeyFor(mutation, store, SEQ);
    const regenerated = freshIdempotencyKey(mutation, store, SEQ);
    expect(regenerated).not.toBe(abandoned);
    expect(idempotencyKeyFor(mutation, store, SEQ)).toBe(regenerated);
  });
});