import { describe, expect, it, vi } from "vitest";
import { ApiClient } from "../../src/services/api/client";
import { readApiConfig } from "../../src/services/api/config";
import type { ApiErrorDetails } from "../../src/services/api/errors";
import { medicationEndpoints } from "../../src/services/api/endpoints/medication";
import { patientsEndpoints } from "../../src/services/api/endpoints/patients";
import {
  createMedicationPlan,
  fetchMedicationPlan,
  fetchMedicationPlans,
  fetchPatientDetail,
  fetchPatients,
} from "../../src/features/doctor/api";
import { createMedicationPlanRequestSchema } from "../../src/services/schemas/medication";
import { patientSummaryResponseSchema } from "../../src/services/schemas/patients";

function jsonResponse(status: number, body: unknown, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), { status, headers });
}

function makeClient(fetchImpl: typeof fetch, resolved?: () => void) {
  return new ApiClient({
    config: readApiConfig({ EXPO_PUBLIC_API_BASE_URL: "http://api.test", ...process.env }),
    fetchImpl,
  });
}

const PLAN_BODY = {
  medication_plan_id: "plan-1",
  patient_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  medication: "Metformin",
  instruction: "500 mg twice daily with food.",
  active: true,
  prescribed_by_role: "doctor",
  created_at: "2026-09-17T09:30:00Z",
};

const PLAN_LIST_BODY = {
  plan_count: 1,
  items: [PLAN_BODY],
};

const PATIENT_BODY = {
  patient_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  uh_id: "UH-001",
  name: "Aarav Sharma",
  facility_id: "facility-1",
  active: true,
  created_at: "2026-01-02T00:00:00Z",
};

describe("doctor medication-plan endpoints (Gate 10F-B → Gate 10F-M)", () => {
  it("fetches the facility plan list via GET /api/v2/clinical/medication-plans", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, PLAN_LIST_BODY));
    const client = makeClient(fetchImpl);

    const list = await fetchMedicationPlans(client);

    const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(String(url)).toBe("http://api.test/api/v2/clinical/medication-plans");
    expect(init.method).toBe("GET");
    expect(list.plan_count).toBe(1);
    expect(list.items[0]).toMatchObject({ medication: "Metformin", patient_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6" });
  });

  it("fetches one plan via GET /api/v2/clinical/medication-plans/{plan_id}", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, PLAN_BODY));
    const client = makeClient(fetchImpl);

    const plan = await fetchMedicationPlan("plan-1", client);

    const [url] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(String(url)).toBe("http://api.test" + medicationEndpoints.planDetail.path("plan-1"));
    expect(plan.medication_plan_id).toBe("plan-1");
    expect(plan.prescribed_by_role).toBe("doctor");
  });

  it("creates a plan POST with ONLY patient_id/medication/instruction + Idempotency-Key", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(200, { medication_plan_id: "plan-new", patient_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6" }),
    );
    const client = makeClient(fetchImpl);

    const result = await createMedicationPlan(
      {
        patient_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        medication: "Metformin",
        instruction: "500 mg once daily.",
      },
      "key-plan-1",
      client,
    );

    const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(String(url)).toBe("http://api.test" + medicationEndpoints.createPlan.path);
    expect(init.method).toBe("POST");
    const headerMap = new Headers(init.headers as Record<string, string>);
    expect(headerMap.get("Idempotency-Key")).toBe("key-plan-1");

    const sent = JSON.parse(String(init.body)) as Record<string, unknown>;
    expect(sent).toEqual({
      patient_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      medication: "Metformin",
      instruction: "500 mg once daily.",
    });
    expect(sent.prescriber).toBeUndefined();
    expect(sent.actor_id).toBeUndefined();
    expect(sent.tenant_id).toBeUndefined();
    expect(sent.facility_id).toBeUndefined();
    expect(result.medication_plan_id).toBe("plan-new");
  });

  it("REJECTS prescriber/actor/tenant/facility fields at the request-schema boundary", () => {
    // The client literally cannot serialize prescriber authorship: the strict
    // request schema refuses any of them before a request can be sent.
    const forbidden = {
      patient_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      medication: "Metformin",
      instruction: "500 mg once daily.",
      prescriber: "Dr. A",
      actor_id: "u-1",
      tenant_id: "tenant-1",
      facility_id: "facility-1",
    };
    expect(createMedicationPlanRequestSchema.safeParse(forbidden).success).toBe(false);

    const allowed = {
      patient_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      medication: "Metformin",
      instruction: "500 mg once daily.",
    };
    expect(createMedicationPlanRequestSchema.safeParse(allowed).success).toBe(true);
  });

  it("maps 409 conflict and 422 field errors for plan creation", async () => {
    const fetches = [
      jsonResponse(409, { error: { code: "CONCURRENT_REQUEST_IN_PROGRESS", message: "Another create is pending." } }),
      jsonResponse(422, {
        error: {
          code: "VALIDATION_ERROR",
          message: "Invalid medication.",
          field_errors: { medication: ["Not a known medication."] },
        },
      }),
    ];
    let call = 0;
    const client = makeClient(vi.fn(async () => fetches[call++]) as typeof fetch);

    const conflict = await createMedicationPlan(
      { patient_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6", medication: "X" },
      "key-2",
      client,
    ).then(
      () => null,
      (err) => err as ApiErrorDetails,
    );
    expect(conflict?.httpStatus).toBe(409);
    expect(conflict?.conflictSubtype).toBe("CONCURRENT_REQUEST_IN_PROGRESS");

    const validation = await createMedicationPlan(
      { patient_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6", medication: "X" },
      "key-2",
      client,
    ).then(
      () => null,
      (err) => err as ApiErrorDetails,
    );
    expect(validation?.httpStatus).toBe(422);
    expect(validation?.fieldErrors?.medication).toEqual(["Not a known medication."]);
  });
});

describe("doctor patient-cohort endpoints (Gate 10F-B → Gate 10F-M)", () => {
  it("fetches the facility cohort via GET /api/v2/patients", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, { patient_count: 1, items: [PATIENT_BODY] }));
    const client = makeClient(fetchImpl);

    const list = await fetchPatients(client);

    const [url] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(String(url)).toBe("http://api.test/api/v2/patients");
    expect(list.items[0]!.uh_id).toBe("UH-001");
  });

  it("fetches one patient via GET /api/v2/patients/{patient_id}", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, PATIENT_BODY));
    const client = makeClient(fetchImpl);

    const patient = await fetchPatientDetail("3fa85f64-5717-4562-b3fc-2c963f66afa6", client);

    const [url] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(String(url)).toBe("http://api.test" + patientsEndpoints.detail.path("3fa85f64-5717-4562-b3fc-2c963f66afa6"));
    expect(patient.name).toBe("Aarav Sharma");
  });

  it("REJECTS PHI (e.g. phone) on the clinician patient schema", () => {
    expect(
      patientSummaryResponseSchema.safeParse({ ...PATIENT_BODY, phone: "555-0100" }).success
    ).toBe(false);
  });
});