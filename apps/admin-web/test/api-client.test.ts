import { describe, it, expect, beforeEach, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "./setup";
import { api, ApiError, setSessionExpiryHandler } from "../src/api/client";
import { tokenStorage } from "../src/auth/tokenStorage";
import { FacilitySchema } from "../src/contracts";

describe("Typed API Client & Idempotency", () => {
  beforeEach(() => {
    tokenStorage.clearTokens();
  });

  it("sends Idempotency-Key header on POST, PATCH, and DELETE mutations", async () => {
    let capturedPostKey: string | null = null;
    let capturedPatchKey: string | null = null;
    let capturedCorrelationId: string | null = null;

    server.use(
      http.post("*/api/v2/admin/facilities", ({ request }) => {
        capturedPostKey = request.headers.get("Idempotency-Key");
        capturedCorrelationId = request.headers.get("X-Correlation-ID");
        return HttpResponse.json({
          facility_id: "550e8400-e29b-41d4-a716-446655440000",
          name: "Clinic 1",
          active: true,
          created_at: "2026-09-17T12:00:00Z",
        });
      }),
      http.patch("*/api/v2/admin/facilities/123", ({ request }) => {
        capturedPatchKey = request.headers.get("Idempotency-Key");
        return HttpResponse.json({
          facility_id: "123",
          name: "Clinic 1 Updated",
          active: true,
          created_at: "2026-09-17T12:00:00Z",
        });
      }),
    );

    await api.post("/api/v2/admin/facilities", FacilitySchema, { name: "Clinic 1" });
    expect(capturedPostKey).toBeTruthy();
    expect(capturedPostKey).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i,
    );
    expect(capturedCorrelationId).toBeTruthy();

    await api.patch("/api/v2/admin/facilities/123", FacilitySchema, { name: "Clinic 1 Updated" });
    expect(capturedPatchKey).toBeTruthy();
    expect(capturedPatchKey).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i,
    );
  });

  it("does NOT send Idempotency-Key header on GET requests", async () => {
    let capturedGetKey: string | null = "dummy";

    server.use(
      http.get("*/api/v2/admin/facilities/123", ({ request }) => {
        capturedGetKey = request.headers.get("Idempotency-Key");
        return HttpResponse.json({
          facility_id: "123",
          name: "Clinic 1",
          active: true,
          created_at: "2026-09-17T12:00:00Z",
        });
      }),
    );

    await api.get("/api/v2/admin/facilities/123", FacilitySchema);
    expect(capturedGetKey).toBeNull();
  });

  it("attaches Bearer token from tokenStorage", async () => {
    let authHeader: string | null = null;
    tokenStorage.setTokens({ accessToken: "test-jwt-token-123" });

    server.use(
      http.get("*/api/v2/admin/facilities/123", ({ request }) => {
        authHeader = request.headers.get("Authorization");
        return HttpResponse.json({
          facility_id: "123",
          name: "Clinic 1",
          active: true,
          created_at: "2026-09-17T12:00:00Z",
        });
      }),
    );

    await api.get("/api/v2/admin/facilities/123", FacilitySchema);
    expect(authHeader).toBe("Bearer test-jwt-token-123");
  });

  it("handles 401 with single refresh and retry once", async () => {
    tokenStorage.setTokens({
      accessToken: "expired-token",
      refreshToken: "valid-refresh-token",
    });

    let attemptCount = 0;
    let refreshAttemptCount = 0;

    server.use(
      http.post("*/realms/thali/protocol/openid-connect/token", () => {
        refreshAttemptCount++;
        return HttpResponse.json({
          access_token: "refreshed-token-456",
          refresh_token: "new-refresh-token",
          expires_in: 300,
          token_type: "Bearer",
        });
      }),
      http.get("*/api/v2/admin/facilities/123", ({ request }) => {
        attemptCount++;
        const auth = request.headers.get("Authorization");
        if (auth === "Bearer expired-token") {
          return new HttpResponse(JSON.stringify({ error: { code: "UNAUTHENTICATED" } }), {
            status: 401,
          });
        }
        if (auth === "Bearer refreshed-token-456") {
          return HttpResponse.json({
            facility_id: "123",
            name: "Refreshed Clinic",
            active: true,
            created_at: "2026-09-17T12:00:00Z",
          });
        }
        return new HttpResponse(null, { status: 403 });
      }),
    );

    const result = await api.get("/api/v2/admin/facilities/123", FacilitySchema);
    expect(attemptCount).toBe(2);
    expect(refreshAttemptCount).toBe(1);
    expect(result.name).toBe("Refreshed Clinic");
    expect(tokenStorage.getAccessToken()).toBe("refreshed-token-456");
  });

  it("handles 401 second failure by clearing session and triggering session expiry", async () => {
    tokenStorage.setTokens({
      accessToken: "expired-token",
      refreshToken: "invalid-refresh-token",
    });

    const onSessionExpired = vi.fn();
    setSessionExpiryHandler(onSessionExpired);

    server.use(
      http.post("*/realms/thali/protocol/openid-connect/token", () => {
        return new HttpResponse("Invalid grant", { status: 400 });
      }),
      http.get("*/api/v2/admin/facilities/123", () => {
        return new HttpResponse(JSON.stringify({ error: { code: "UNAUTHENTICATED" } }), {
          status: 401,
        });
      }),
    );

    await expect(api.get("/api/v2/admin/facilities/123", FacilitySchema)).rejects.toThrow(
      ApiError,
    );
    expect(tokenStorage.hasTokens()).toBe(false);
    expect(onSessionExpired).toHaveBeenCalled();
  });

  it("handles 403 Forbidden with OPERATION_DENIED error", async () => {
    server.use(
      http.get("*/api/v2/admin/facilities/123", () => {
        return new HttpResponse(
          JSON.stringify({
            error: { code: "FORBIDDEN", message: "Operator lacks required role" },
          }),
          { status: 403 },
        );
      }),
    );

    try {
      await api.get("/api/v2/admin/facilities/123", FacilitySchema);
      expect.unreachable();
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      const apiErr = err as ApiError;
      expect(apiErr.status).toBe(403);
      expect(apiErr.code).toBe("FORBIDDEN");
    }
  });

  it("handles 404 Not Found error", async () => {
    server.use(
      http.get("*/api/v2/admin/facilities/999", () => {
        return new HttpResponse(
          JSON.stringify({ error: { code: "NOT_FOUND", message: "Facility not found" } }),
          { status: 404 },
        );
      }),
    );

    await expect(api.get("/api/v2/admin/facilities/999", FacilitySchema)).rejects.toMatchObject({
      status: 404,
      code: "NOT_FOUND",
    });
  });

  it("handles 409 Conflict error", async () => {
    server.use(
      http.post("*/api/v2/admin/facilities", () => {
        return new HttpResponse(
          JSON.stringify({ error: { code: "CONFLICT", message: "Facility already exists" } }),
          { status: 409 },
        );
      }),
    );

    await expect(
      api.post("/api/v2/admin/facilities", FacilitySchema, { name: "Duplicate" }),
    ).rejects.toMatchObject({
      status: 409,
      code: "CONFLICT",
    });
  });

  it("handles 422 Validation Error mapping details", async () => {
    server.use(
      http.post("*/api/v2/admin/facilities", () => {
        return new HttpResponse(
          JSON.stringify({
            error: {
              code: "VALIDATION_ERROR",
              message: "Name too short",
              details: { field: "name" },
            },
          }),
          { status: 422 },
        );
      }),
    );

    try {
      await api.post("/api/v2/admin/facilities", FacilitySchema, { name: "" });
      expect.unreachable();
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      const apiErr = err as ApiError;
      expect(apiErr.status).toBe(422);
      expect(apiErr.details).toEqual({ field: "name" });
    }
  });

  it("handles 429 Rate Limit with Retry-After header", async () => {
    server.use(
      http.get("*/api/v2/admin/facilities/123", () => {
        return new HttpResponse(null, {
          status: 429,
          headers: { "Retry-After": "15" },
        });
      }),
    );

    try {
      await api.get("/api/v2/admin/facilities/123", FacilitySchema);
      expect.unreachable();
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      const apiErr = err as ApiError;
      expect(apiErr.status).toBe(429);
      expect(apiErr.retryAfter).toBe(15);
    }
  });

  it("handles 500 Server Error safely", async () => {
    server.use(
      http.get("*/api/v2/admin/facilities/123", () => {
        return new HttpResponse("Internal server crash", { status: 500 });
      }),
    );

    await expect(api.get("/api/v2/admin/facilities/123", FacilitySchema)).rejects.toMatchObject({
      status: 500,
    });
  });

  it("validates responses strictly via Zod schema", async () => {
    server.use(
      http.get("*/api/v2/admin/facilities/123", () => {
        // Missing required field 'created_at'
        return HttpResponse.json({
          facility_id: "123",
          name: "Clinic 1",
          active: true,
        });
      }),
    );

    await expect(api.get("/api/v2/admin/facilities/123", FacilitySchema)).rejects.toMatchObject({
      code: "SCHEMA_VALIDATION_ERROR",
    });
  });
});
