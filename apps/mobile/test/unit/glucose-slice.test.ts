import { describe, expect, it, vi } from "vitest";
import {
  glucoseFormInputSchema,
  ingestGlucoseResponseSchema,
  patientObservationFeedSchema,
} from "../../src/services/schemas/clinical";
import { glucoseKeys } from "../../src/features/glucose/types";
import { fetchObservationFeed, submitGlucoseReading } from "../../src/features/glucose/api";
import { isPatientSafeObservation, assertPatientSafeFeed } from "../../src/features/glucose/feedSafety";
import { isUuidV4, secureUuid } from "../../src/services/api/correlation";
import { mapHttpError } from "../../src/services/api/errors";
import { readApiConfig } from "../../src/services/api/config";
import { ApiClient } from "../../src/services/api/client";
import { InMemoryIdempotencyKeyStore, idempotencyKeyFor } from "../../src/services/api/idempotency";

describe("Gate 10D: Patient Glucose Vertical Slice Unit Tests", () => {
  // Scenario 1: Valid glucose entry schema validation
  it("validates valid glucose entry schemas with tags", () => {
    const validFasting = glucoseFormInputSchema.safeParse({
      value_mg_dl: 110,
      tag: "fasting",
    });
    expect(validFasting.success).toBe(true);

    const validPostBreakfast = glucoseFormInputSchema.safeParse({
      value_mg_dl: 145,
      tag: "postbreakfast",
    });
    expect(validPostBreakfast.success).toBe(true);

    const validNoTag = glucoseFormInputSchema.safeParse({
      value_mg_dl: 95,
      tag: null,
    });
    expect(validNoTag.success).toBe(true);
  });

  // Scenario 2: Invalid glucose entry schema validation
  it("rejects invalid glucose entry schemas (non-integer, strings, negative)", () => {
    const decimal = glucoseFormInputSchema.safeParse({ value_mg_dl: 110.5 });
    expect(decimal.success).toBe(false);

    const nonNumeric = glucoseFormInputSchema.safeParse({ value_mg_dl: "invalid-string" });
    expect(nonNumeric.success).toBe(false);

    const decimalString = glucoseFormInputSchema.safeParse({ value_mg_dl: "110.5" });
    expect(decimalString.success).toBe(false);

    const nanVal = glucoseFormInputSchema.safeParse({ value_mg_dl: NaN });
    expect(nanVal.success).toBe(false);

    const negative = glucoseFormInputSchema.safeParse({ value_mg_dl: -50 });
    expect(negative.success).toBe(false);
  });

  // Scenario 3: Out-of-range glucose entry rejected (< 20 or > 600 mg/dL)
  it("rejects out-of-range glucose entries (< 20 or > 600 mg/dL)", () => {
    const belowMin = glucoseFormInputSchema.safeParse({ value_mg_dl: 19 });
    expect(belowMin.success).toBe(false);
    if (!belowMin.success) {
      expect(belowMin.error?.issues[0]?.message).toContain("at least 20");
    }

    const aboveMax = glucoseFormInputSchema.safeParse({ value_mg_dl: 601 });
    expect(aboveMax.success).toBe(false);
    if (!aboveMax.success) {
      expect(aboveMax.error?.issues[0]?.message).toContain("at most 600");
    }

    const atMin = glucoseFormInputSchema.safeParse({ value_mg_dl: 20 });
    expect(atMin.success).toBe(true);

    const atMax = glucoseFormInputSchema.safeParse({ value_mg_dl: 600 });
    expect(atMax.success).toBe(true);
  });

  // Scenario 4: Request construction includes Idempotency-Key and X-Correlation-ID
  it("constructs ingest request with required headers and payload", async () => {
    const fetchImpl = vi.fn(async () =>
      new Response(
        JSON.stringify({
          observation_id: "obs-100",
          patient_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
          value_mg_dl: 125,
          taken_at: "2026-09-17T08:00:00Z",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      )
    );

    const client = new ApiClient({
      config: readApiConfig({ EXPO_PUBLIC_API_BASE_URL: "http://api.test", ...process.env }),
      fetchImpl: fetchImpl as typeof fetch,
      createCorrelationId: () => "corr-uuid-1234",
    });

    const idempotencyKey = "idem-uuid-5678";
    await submitGlucoseReading(
      {
        patient_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        value_mg_dl: 125,
        tag: "fasting",
      },
      idempotencyKey,
      client,
      "test-bearer-token"
    );

    expect(fetchImpl).toHaveBeenCalledOnce();
    const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(String(url)).toBe("http://api.test/api/v2/clinical/observations");
    expect(init.method).toBe("POST");

    const headers = new Headers(init.headers as Record<string, string>);
    expect(headers.get("Idempotency-Key")).toBe("idem-uuid-5678");
    expect(headers.get("X-Correlation-ID")).toBe("corr-uuid-1234");
    expect(headers.get("Authorization")).toBe("Bearer test-bearer-token");
    expect(headers.get("Content-Type")).toBe("application/json");

    const parsedBody = JSON.parse(init.body as string);
    expect(parsedBody.patient_id).toBe("3fa85f64-5717-4562-b3fc-2c963f66afa6");
    expect(parsedBody.value_mg_dl).toBe(125);
    expect(parsedBody.tag).toBe("fasting");
  });

  // Scenario 5: Response validation parses IngestGlucoseResponse
  it("validates and parses IngestGlucoseResponse", () => {
    const rawResponse = {
      observation_id: "obs-abc-123",
      patient_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      value_mg_dl: 130,
      taken_at: "2026-09-17T08:30:00Z",
    };
    const parsed = ingestGlucoseResponseSchema.safeParse(rawResponse);
    expect(parsed.success).toBe(true);
    if (parsed.success) {
      expect(parsed.data.observation_id).toBe("obs-abc-123");
      expect(parsed.data.value_mg_dl).toBe(130);
      expect(parsed.data.patient_id).toBe("3fa85f64-5717-4562-b3fc-2c963f66afa6");
    }
  });

  // Scenario 6: Timestamp serialization converts Date/ISO string correctly
  it("serializes taken_at as ISO-8601 timestamp string", async () => {
    const fetchImpl = vi.fn(async () =>
      new Response(
        JSON.stringify({
          observation_id: "obs-200",
          patient_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
          value_mg_dl: 100,
          taken_at: "2026-09-17T08:45:00.000Z",
        }),
        { status: 200 }
      )
    );

    const client = new ApiClient({
      config: readApiConfig({ EXPO_PUBLIC_API_BASE_URL: "http://api.test", ...process.env }),
      fetchImpl: fetchImpl as typeof fetch,
    });

    const nowIso = new Date("2026-09-17T08:45:00.000Z").toISOString();
    await submitGlucoseReading(
      {
        patient_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        value_mg_dl: 100,
        taken_at: nowIso,
      },
      "idem-1",
      client
    );

    const [, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    const body = JSON.parse(init.body as string);
    expect(body.taken_at).toBe("2026-09-17T08:45:00.000Z");
  });

  // Scenario 7: Query key stability
  it("provides deterministic and stable query keys for glucose feeds", () => {
    const patientId = "3fa85f64-5717-4562-b3fc-2c963f66afa6";
    expect(glucoseKeys.all).toEqual(["clinical"]);
    expect(glucoseKeys.observations()).toEqual(["clinical", "observations"]);
    expect(glucoseKeys.feed(patientId)).toEqual(["clinical", "observations", patientId]);
    expect(glucoseKeys.feed(patientId)).toEqual(glucoseKeys.feed(patientId));
  });

  // Scenario 8: Idempotency key generation: produces valid UUID v4
  it("generates RFC 4122 compliant UUID v4 idempotency keys", () => {
    const key = secureUuid();
    expect(isUuidV4(key)).toBe(true);
    expect(key).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i);
  });

  // Scenario 9: Idempotency key reuse: multiple attempts with same mutation reuse identical key
  it("reuses the exact same idempotency key for identical logical mutations across retries", () => {
    const store = new InMemoryIdempotencyKeyStore();
    const mutation = "obs:patient-1:reading-1";
    const key1 = idempotencyKeyFor(mutation, store);
    const key2 = idempotencyKeyFor(mutation, store);
    expect(key1).toBe(key2);
  });

  // Scenario 10: Idempotency key preserved across auth retry on 401
  it("preserves idempotency key across 401 retry", async () => {
    let callCount = 0;
    const recordedKeys: string[] = [];

    const fetchImpl = vi.fn(async (_url: string, init?: RequestInit) => {
      callCount++;
      const headers = new Headers(init?.headers as Record<string, string>);
      recordedKeys.push(headers.get("Idempotency-Key") ?? "");

      if (callCount === 1) {
        return new Response(JSON.stringify({ error: { code: "AUTHENTICATION_EXPIRED" } }), {
          status: 401,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response(
        JSON.stringify({
          observation_id: "obs-retry-success",
          patient_id: "p-1",
          value_mg_dl: 115,
          taken_at: "2026-09-17T09:00:00Z",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    });

    const client = new ApiClient({
      config: readApiConfig({ EXPO_PUBLIC_API_BASE_URL: "http://api.test", ...process.env }),
      fetchImpl: fetchImpl as typeof fetch,
    });

    const idempotencyKey = "idem-stable-uuid";

    // First attempt fails with 401
    await expect(
      submitGlucoseReading(
        { patient_id: "p-1", value_mg_dl: 115 },
        idempotencyKey,
        client,
        "expired-token"
      )
    ).rejects.toThrow();

    // Second attempt (after token refresh) retries with the same idempotency key
    const success = await submitGlucoseReading(
      { patient_id: "p-1", value_mg_dl: 115 },
      idempotencyKey,
      client,
      "fresh-token"
    );

    expect(success.observation_id).toBe("obs-retry-success");
    expect(recordedKeys).toEqual(["idem-stable-uuid", "idem-stable-uuid"]);
  });

  // Scenario 11: 403 Forbidden mapped to appropriate user-facing error
  it("maps 403 Forbidden to structured FORBIDDEN error kind", () => {
    const error = mapHttpError({
      status: 403,
      body: { error: { code: "AUTHORIZATION_DENIED", message: "Patient inactive" } },
    });
    expect(error.kind).toBe("FORBIDDEN");
    expect(error.httpStatus).toBe(403);
    expect(error.message).toContain("Patient inactive");
  });

  // Scenario 12: 409 Conflict mapped to concurrent submission error
  it("maps 409 Conflict with CONCURRENT_REQUEST_IN_PROGRESS subtype", () => {
    const error = mapHttpError({
      status: 409,
      body: {
        error: {
          code: "CONCURRENT_REQUEST_IN_PROGRESS",
          message: "Operation in progress with key",
        },
      },
    });
    expect(error.kind).toBe("CONFLICT");
    expect(error.conflictSubtype).toBe("CONCURRENT_REQUEST_IN_PROGRESS");
    expect(error.httpStatus).toBe(409);
  });

  // Scenario 13: 422 Unprocessable Entity mapped to field validation error
  it("maps 422 Unprocessable Entity to VALIDATION_ERROR kind", () => {
    const error = mapHttpError({
      status: 422,
      body: {
        error: {
          code: "VALIDATION_ERROR",
          message: "Input validation failed",
          details: [{ loc: ["body", "value_mg_dl"], msg: "ensure this value is greater than or equal to 20" }],
        },
      },
    });
    expect(error.kind).toBe("VALIDATION_ERROR");
    expect(error.httpStatus).toBe(422);
  });

  // Scenario 14: 429 Rate Limit mapped with Retry-After header extraction
  it("maps 429 Rate Limit with parsed Retry-After header", () => {
    const headers = new Headers();
    headers.set("Retry-After", "45");

    const error = mapHttpError({
      status: 429,
      headers,
      body: { error: { code: "RATE_LIMIT_EXCEEDED", message: "Too many submissions" } },
    });
    expect(error.kind).toBe("RATE_LIMITED");
    expect(error.httpStatus).toBe(429);
    expect(error.retryAfterSeconds).toBe(45);
  });

  // Scenario 15: Patient DTO strictly omits forbidden clinician fields
  it("enforces clinical asymmetry: patient observation schema strictly excludes clinician-only fields", () => {
    // Contaminated payload with clinician-only fields must be REJECTED by strict schema
    const contaminatedPayload = {
      patient_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      items: [
        {
          kind: "glucose",
          value_mg_dl: 120,
          tag: "fasting",
          taken_at: "2026-09-17T07:00:00Z",
          confirmed: true,
          carbs_grams: 45,
          glycemic_index: "55",
          risk_score: 0.82,
          diagnostic_advice: "Increase basal insulin",
        },
      ],
    };

    const contaminatedResult = patientObservationFeedSchema.safeParse(contaminatedPayload);
    expect(contaminatedResult.success).toBe(false);
    if (!contaminatedResult.success) {
      const issue = contaminatedResult.error.issues[0];
      expect(issue?.message).toContain("Unrecognized key(s)");
    }

    // Valid patient-facing payload must pass cleanly
    const validPatientPayload = {
      patient_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      items: [
        {
          kind: "glucose",
          value_mg_dl: 120,
          tag: "fasting",
          taken_at: "2026-09-17T07:00:00Z",
          confirmed: true,
        },
      ],
    };

    const validResult = patientObservationFeedSchema.safeParse(validPatientPayload);
    expect(validResult.success).toBe(true);
    if (validResult.success) {
      const item = validResult.data.items[0];
      expect(item?.kind).toBe("glucose");
      const record = item as unknown as Record<string, unknown>;
      expect(record.carbs_grams).toBeUndefined();
      expect(record.glycemic_index).toBeUndefined();
      expect(record.risk_score).toBeUndefined();
      expect(record.diagnostic_advice).toBeUndefined();
      expect(() => assertPatientSafeFeed(validResult.data)).not.toThrow();
    }
  });

  // Scenario 16: Observation feed GET constructs patient_id + limit query
  it("constructs observation feed GET with patient_id and limit", async () => {
    const patientId = "3fa85f64-5717-4562-b3fc-2c963f66afa6";
    const fetchImpl = vi.fn(async () =>
      new Response(JSON.stringify({ patient_id: patientId, items: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );

    const client = new ApiClient({
      config: readApiConfig({ EXPO_PUBLIC_API_BASE_URL: "http://api.test", ...process.env }),
      fetchImpl: fetchImpl as typeof fetch,
    });

    const feed = await fetchObservationFeed(patientId, 50, client);
    expect(feed.items).toEqual([]);
    expect(feed.patient_id).toBe(patientId);

    const [url] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(String(url)).toContain("/api/v2/clinical/observations?patient_id=" + encodeURIComponent(patientId));
    expect(String(url)).toContain("limit=50");
  });

  // Scenario 17: Information-asymmetry guard refuses contaminated patient feeds
  it("refuses patient-facing observations that contain clinician-only fields", async () => {
    const safeItem = {
      kind: "glucose",
      value_mg_dl: 120,
      tag: "fasting",
      taken_at: "2026-09-17T07:00:00Z",
      confirmed: true,
    };
    expect(isPatientSafeObservation(safeItem)).toBe(true);
    expect(isPatientSafeObservation({ ...safeItem, carbs_grams: 45 })).toBe(false);
    expect(isPatientSafeObservation({ ...safeItem, glycemic_index: "55" })).toBe(false);

    // Defence-in-depth: a contaminated feed is refused before it reaches any screen.
    const patientId = "3fa85f64-5717-4562-b3fc-2c963f66afa6";
    const fetchImpl = vi.fn(async () =>
      new Response(
        JSON.stringify({
          patient_id: patientId,
          items: [{ ...safeItem, carbs_grams: 45, glycemic_index: "55" }],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      )
    );

    const client = new ApiClient({
      config: readApiConfig({ EXPO_PUBLIC_API_BASE_URL: "http://api.test", ...process.env }),
      fetchImpl: fetchImpl as typeof fetch,
    });

    await expect(fetchObservationFeed(patientId, 50, client)).rejects.toThrow();
  });
});
