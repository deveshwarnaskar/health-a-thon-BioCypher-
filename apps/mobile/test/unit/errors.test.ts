import { describe, expect, it } from "vitest";
import {
  isAuthExpiredSignal,
  mapHttpError,
  mapNetworkError,
  parseRetryAfter,
} from "../../src/services/api/errors";

function headersWithRetryAfter(value: string): Headers {
  const headers = new Headers();
  headers.set("Retry-After", value);
  return headers;
}

function errorBody(code: string, message = "safe message") {
  return { error: { code, message, correlation_id: "corr-1" } };
}

describe("HTTP error model (Gate 10A §9)", () => {
  it("maps 401 to the auth-expired signal kind", () => {
    const error = mapHttpError({
      status: 401,
      body: errorBody("AUTHENTICATION_EXPIRED"),
    });
    expect(isAuthExpiredSignal(error)).toBe(true);
    expect(error.kind).toBe("UNAUTHORIZED");
    expect(error.code).toBe("AUTHENTICATION_EXPIRED");
  });

  it("maps 403 to FORBIDDEN with a structured reason for capability denial", () => {
    const error = mapHttpError({
      status: 403,
      body: errorBody("MEDICATION_PLAN_UNAUTHORIZED"),
    });
    expect(error.kind).toBe("FORBIDDEN");
    expect(error.forbiddenReason).toBe("insufficient_capability");
  });

  it("keeps 403 generic denials as authorization_denied", () => {
    const error = mapHttpError({ status: 403, body: errorBody("AUTHORIZATION_DENIED") });
    expect(error.forbiddenReason).toBe("authorization_denied");
  });

  it("maps 409 conflicts and classifies the idempotency subtypes", () => {
    const concurrent = mapHttpError({
      status: 409,
      body: errorBody("CONCURRENT_REQUEST_IN_PROGRESS"),
    });
    expect(concurrent.kind).toBe("CONFLICT");
    expect(concurrent.conflictSubtype).toBe("CONCURRENT_REQUEST_IN_PROGRESS");

    const mismatch = mapHttpError({
      status: 409,
      body: errorBody("IDEMPOTENCY_KEY_MISMATCH"),
    });
    expect(mismatch.conflictSubtype).toBe("IDEMPOTENCY_KEY_MISMATCH");
  });

  it("maps 404/400/413/422 to their dedicated kinds", () => {
    expect(mapHttpError({ status: 404, body: errorBody("RESOURCE_NOT_FOUND") }).kind).toBe(
      "NOT_FOUND",
    );
    expect(mapHttpError({ status: 400, body: errorBody("INVALID_REQUEST") }).kind).toBe(
      "INVALID_REQUEST",
    );
    expect(mapHttpError({ status: 413, body: errorBody("PAYLOAD_TOO_LARGE") }).kind).toBe(
      "PAYLOAD_TOO_LARGE",
    );
    const validation = mapHttpError({ status: 422, body: errorBody("VALIDATION_ERROR") });
    expect(validation.kind).toBe("VALIDATION_ERROR");
  });

  it("maps all 5xx to SERVER_ERROR for 500/502/503/504", () => {
    for (const status of [500, 502, 503, 504]) {
      expect(mapHttpError({ status }).kind).toBe("SERVER_ERROR");
      expect(mapHttpError({ status }).message).not.toMatch(/stack|trace/i);
    }
  });

  it("maps missing/empty status to UNKNOWN", () => {
    expect(mapHttpError({ status: 499 }).kind).toBe("UNKNOWN");
  });

  it("never surfaces stack traces or raw exception text", () => {
    const error = mapHttpError({
      status: 500,
      body: { error: { message: "ValueError: traceback ... secret" } },
    });
    // Safe, generic server message wins; raw internals are dropped.
    expect(error.message).not.toMatch(/ValueError|traceback|secret/);
  });
});

describe("429 rate-limit handling", () => {
  it("parses integer Retry-After seconds", () => {
    expect(parseRetryAfter("120")).toBe(120);
  });

  it("parses HTTP-date Retry-After", () => {
    const now = new Date("2026-01-01T00:00:00Z");
    const later = new Date(now.getTime() + 60_000).toUTCString();
    expect(parseRetryAfter(later, now)).toBe(60);
  });

  it("returns undefined for malformed Retry-After values", () => {
    expect(parseRetryAfter("-5")).toBeUndefined();
    expect(parseRetryAfter("garbage")).toBeUndefined();
    expect(parseRetryAfter("")).toBeUndefined();
  });

  it("exposes retryAfterSeconds from a 429 with Retry-After header", () => {
    const error = mapHttpError({
      status: 429,
      body: errorBody("RATE_LIMIT_EXCEEDED"),
      headers: headersWithRetryAfter("30"),
    });
    expect(error.kind).toBe("RATE_LIMITED");
    expect(error.retryAfterSeconds).toBe(30);
  });
});

describe("network errors", () => {
  it("normalises fetch rejections to NETWORK_ERROR", () => {
    const error = mapNetworkError(new TypeError("fetch failed"));
    expect(error.kind).toBe("NETWORK_ERROR");
    expect(error.httpStatus).toBe(0);
  });
});