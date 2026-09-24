import { describe, expect, it, vi } from "vitest";
import { fetchCaregiverPatients } from "../../src/features/caregiver/api";
import { caregiverEndpoints } from "../../src/services/api/endpoints/caregiver";
import { ApiClient } from "../../src/services/api/client";
import { readApiConfig } from "../../src/services/api/config";
import { mapHttpError } from "../../src/services/api/errors";

const validListResponse = {
  patient_count: 1,
  items: [
    {
      relationship_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      patient_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      relationship_label: "test-caregiver",
      status: "verified",
      capabilities: ["read_glucose", "read_meal"],
      expires_at: null,
      name: "Aarav Sharma",
    },
  ],
};

function makeClient(fetchImpl: typeof fetch) {
  return new ApiClient({
    config: readApiConfig({ EXPO_PUBLIC_API_BASE_URL: "http://api.test", ...process.env }),
    fetchImpl,
    createCorrelationId: () => "corr-uuid-1234",
  });
}

describe("Gate 10E-M: Caregiver Patient Discovery API", () => {
  // Scenario 1: GET list constructs the exact contract path with auth headers
  it("constructs GET /api/v2/caregivers/me/patients with bearer token and correlation id", async () => {
    const fetchImpl = vi.fn(async () =>
      new Response(JSON.stringify(validListResponse), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );

    const list = await fetchCaregiverPatients(makeClient(fetchImpl as typeof fetch), "test-bearer-token");

    expect(list.patient_count).toBe(1);
    expect(list.items[0]?.name).toBe("Aarav Sharma");

    expect(fetchImpl).toHaveBeenCalledOnce();
    const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(String(url)).toBe("http://api.test/api/v2/caregivers/me/patients");
    expect(init.method).toBe("GET");

    const headers = new Headers(init.headers as Record<string, string>);
    expect(headers.get("Authorization")).toBe("Bearer test-bearer-token");
    expect(headers.get("X-Correlation-ID")).toBe("corr-uuid-1234");
    expect(headers.get("Accept")).toBe("application/json");
  });

  // Scenario 2: GET never sends a body or an Idempotency-Key
  it("sends no body and no Idempotency-Key on a non-mutating GET", async () => {
    const fetchImpl = vi.fn(async () =>
      new Response(JSON.stringify({ patient_count: 0, items: [] }), { status: 200 })
    );

    await fetchCaregiverPatients(makeClient(fetchImpl as typeof fetch));

    const [, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(init.body).toBeUndefined();

    const headers = new Headers((init.headers ?? {}) as Record<string, string>);
    expect(headers.get("Idempotency-Key")).toBeNull();
    expect(headers.get("Content-Type")).toBeNull();
  });

  // Scenario 3: Endpoint definition flags GET as non-idempotent (no key)
  it("declares the patient list endpoint idempotency-free", () => {
    expect(caregiverEndpoints.patients.method).toBe("GET");
    expect(caregiverEndpoints.patients.requiresIdempotencyKey).toBe(false);
  });

  // Scenario 4: Client contract mismatch — contaminated DTO is refused
  it("refuses a response that carries clinician-only analytics fields", async () => {
    const contaminated = {
      patient_count: 1,
      items: [
        {
          ...validListResponse.items[0],
          risk_score: 0.82,
          glycemic_index: "55",
        },
      ],
    };

    const fetchImpl = vi.fn(async () =>
      new Response(JSON.stringify(contaminated), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );

    let thrown: { code?: string; httpStatus?: number } | undefined;
    try {
      await fetchCaregiverPatients(makeClient(fetchImpl as typeof fetch));
    } catch (error) {
      thrown = error as { code?: string; httpStatus?: number };
    }
    expect(thrown?.code).toBe("CLIENT_CONTRACT_MISMATCH");
    expect(thrown?.httpStatus).toBe(200);
  });

  // Scenario 5: A null capabilities array is refused by the schema
  it("refuses a response whose capabilities are missing/null", async () => {
    const malformed = {
      patient_count: 1,
      items: [{ ...validListResponse.items[0], capabilities: null }],
    };
    const fetchImpl = vi.fn(async () =>
      new Response(JSON.stringify(malformed), { status: 200 })
    );

    await expect(fetchCaregiverPatients(makeClient(fetchImpl as typeof fetch))).rejects.toThrow();
  });

  // Scenario 6: 403 maps to structured FORBIDDEN error kind
  it("maps 403 to FORBIDDEN with the backend denial code", async () => {
    const fetchImpl = vi.fn(async () =>
      new Response(
        JSON.stringify({
          error: { code: "AUTHORIZATION_DENIED", message: "Caregiver not authorized" },
        }),
        { status: 403, headers: { "Content-Type": "application/json" } }
      )
    );

    let thrown: { kind?: string; httpStatus?: number; code?: string } | undefined;
    try {
      await fetchCaregiverPatients(makeClient(fetchImpl as typeof fetch));
    } catch (error) {
      thrown = error as { kind?: string; httpStatus?: number; code?: string };
    }
    expect(thrown?.kind).toBe("FORBIDDEN");
    expect(thrown?.httpStatus).toBe(403);
    expect(thrown?.code).toBe("AUTHORIZATION_DENIED");
  });

  // Scenario 7: 401 is preserved as the single auth-expired signal (not retried)
  it("maps 401 to the auth-expired UNAUTHORIZED signal", async () => {
    const fetchImpl = vi.fn(async () =>
      new Response(
        JSON.stringify({ error: { code: "AUTHENTICATION_EXPIRED", message: "Expired" } }),
        { status: 401, headers: { "Content-Type": "application/json" } }
      )
    );

    let thrown: { kind?: string; httpStatus?: number } | undefined;
    try {
      await fetchCaregiverPatients(makeClient(fetchImpl as typeof fetch));
    } catch (error) {
      thrown = error as { kind?: string; httpStatus?: number };
    }
    expect(thrown?.kind).toBe("UNAUTHORIZED");
    expect(thrown?.httpStatus).toBe(401);
  });

  // Scenario 8: Error mapping parity — 429 respects Retry-After
  it("maps 429 with parsed Retry-After header via shared error mapper", () => {
    const headers = new Headers();
    headers.set("Retry-After", "30");
    const error = mapHttpError({
      status: 429,
      headers,
      body: { error: { code: "RATE_LIMIT_EXCEEDED", message: "Too many requests" } },
    });
    expect(error.kind).toBe("RATE_LIMITED");
    expect(error.httpStatus).toBe(429);
    expect(error.retryAfterSeconds).toBe(30);
  });
});