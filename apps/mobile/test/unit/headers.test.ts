import { describe, expect, it } from "vitest";
import {
  assembleHeaders,
  HEADER_ACCEPT,
  HEADER_AUTHORIZATION,
  HEADER_CONTENT_TYPE,
  HEADER_CORRELATION_ID,
  HEADER_IDEMPOTENCY_KEY,
} from "../../src/services/api/headers";

describe("request header assembly", () => {
  it("injects the Authorization: Bearer header when a token is provided", () => {
    const headers = assembleHeaders({ token: "abc.def.ghi", correlationId: "corr-1" });
    expect(headers[HEADER_AUTHORIZATION]).toBe("Bearer abc.def.ghi");
  });

  it("omits the Authorization header when no token is present", () => {
    const headers = assembleHeaders({ correlationId: "corr-1" });
    expect(headers[HEADER_AUTHORIZATION]).toBeUndefined();
  });

  it("always carries the X-Correlation-ID", () => {
    const headers = assembleHeaders({ correlationId: "5ab67e77-1111-4111-8111-000000000001" });
    expect(headers[HEADER_CORRELATION_ID]).toBe("5ab67e77-1111-4111-8111-000000000001");
  });

  it("attaches Content-Type only for body-carrying requests", () => {
    expect(assembleHeaders({ correlationId: "c" }).hasOwnProperty(HEADER_CONTENT_TYPE)).toBe(false);
    expect(assembleHeaders({ correlationId: "c", hasBody: true })[HEADER_CONTENT_TYPE]).toBe(
      "application/json",
    );
  });

  it("accepts application/json on every request", () => {
    expect(assembleHeaders({ correlationId: "c" })[HEADER_ACCEPT]).toBe("application/json");
  });

  it("adds the Idempotency-Key for mutation requests", () => {
    const headers = assembleHeaders({
      correlationId: "c",
      idempotencyKey: "d4f76c0a-8f2a-4f2a-9e9a-123456789abc",
    });
    expect(headers[HEADER_IDEMPOTENCY_KEY]).toBe("d4f76c0a-8f2a-4f2a-9e9a-123456789abc");
  });
});