import { describe, expect, it, vi } from "vitest";
import { readApiConfig, ApiConfigError } from "../../src/services/api/config";
import { ApiClient } from "../../src/services/api/client";
import { isAuthExpiredSignal } from "../../src/services/api/errors";
import { patientObservationFeedSchema, type PatientObservationFeedResponse } from "../../src/services/schemas/clinical";

function jsonResponse(status: number, body: unknown, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), { status, headers });
}

describe("ApiClient integration", () => {
  it("invokes a 401 auth-expired signal hook on Unauthorized", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(401, {}));
    const onAuthExpired = vi.fn();
    const client = new ApiClient({
      config: readApiConfig({
        EXPO_PUBLIC_API_BASE_URL: "http://api.test",
        ...process.env,
      }),
      fetchImpl: fetchImpl as typeof fetch,
    });

    await expect(client.request({ method: "GET", path: "/api/v2/auth/verify" })).rejects.toThrow();

    const thrown = await client
      .request({ method: "GET", path: "/api/v2/auth/verify", onAuthExpired })
      .then(
        () => null,
        (error) => error,
      );
    expect(isAuthExpiredSignal(thrown)).toBe(true);
    expect(onAuthExpired).toHaveBeenCalledOnce();
  });

  it("sends X-Correlation-ID and bearer header on every authenticated request", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, { patient_id: "p-1", items: [] }));
    const client = new ApiClient({
      config: readApiConfig({ EXPO_PUBLIC_API_BASE_URL: "http://api.test", ...process.env }),
      fetchImpl: fetchImpl as typeof fetch,
      createCorrelationId: () => "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    });

    await client.request<PatientObservationFeedResponse>({
      method: "GET",
      path: "/api/v2/clinical/observations",
      token: "tok-1",
      schema: patientObservationFeedSchema,
    });

    const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(String(url)).toBe("http://api.test/api/v2/clinical/observations");
    expect(init.headers).toEqual({
      Accept: "application/json",
      "X-Correlation-ID": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      Authorization: "Bearer tok-1",
    });
  });

  it("attaches Idempotency-Key and Content-Type for mutations", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, {
      observation_id: "obs-9",
      patient_id: "p-1",
      value_mg_dl: 120,
      taken_at: "2026-09-16T10:00:00Z",
    }));
    const client = new ApiClient({
      config: readApiConfig({ EXPO_PUBLIC_API_BASE_URL: "http://api.test", ...process.env }),
      fetchImpl: fetchImpl as typeof fetch,
    });

    await client.request({
      method: "POST",
      path: "/api/v2/clinical/observations",
      body: { patient_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6", value_mg_dl: 120 },
      idempotencyKey: "d4f76c0a-8f2a-4f2a-9e9a-123456789abc",
    });

    const [, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    const headerMap = new Headers(init.headers as Record<string, string>);
    expect(headerMap.get("Idempotency-Key")).toBe("d4f76c0a-8f2a-4f2a-9e9a-123456789abc");
    expect(headerMap.get("Content-Type")).toBe("application/json");
  });

  it("rejects with a contract-mismatch error when a 200 body fails schema parse", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, { patient_id: "p" }));
    const client = new ApiClient({
      config: readApiConfig({ EXPO_PUBLIC_API_BASE_URL: "http://api.test", ...process.env }),
      fetchImpl: fetchImpl as typeof fetch,
    });

    const error = await client
      .request({ method: "GET", path: "/api/v2/clinical/observations", schema: patientObservationFeedSchema })
      .then(
        () => null,
        (err) => err,
      );
    expect(error.code).toBe("CLIENT_CONTRACT_MISMATCH");
  });

  it("refuses to fire before a base URL is configured", async () => {
    const fetchImpl = vi.fn();
    const client = new ApiClient({
      config: readApiConfig({}),
      fetchImpl: fetchImpl as typeof fetch,
    });
    await expect(client.request({ method: "GET", path: "/x" })).rejects.toBeInstanceOf(ApiConfigError);
    expect(fetchImpl).not.toHaveBeenCalled();
  });
});