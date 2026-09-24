import { describe, expect, it } from "vitest";
import { isUuidV4, newCorrelationId } from "../../src/services/api/correlation";

describe("correlation ID generation", () => {
  it("generates a deterministic-shape UUIDv4 for every request", () => {
    const id = newCorrelationId();
    expect(isUuidV4(id)).toBe(true);
  });

  it("never reuses a correlation ID across requests", () => {
    const first = newCorrelationId();
    const second = newCorrelationId();
    expect(first).not.toBe(second);
  });

  it("rejects malformed identifiers", () => {
    expect(isUuidV4("not-a-uuid")).toBe(false);
    expect(isUuidV4("")).toBe(false);
    expect(isUuidV4("550e8400-e29b-41d4-a716-446655440000")).toBe(true);
  });
});