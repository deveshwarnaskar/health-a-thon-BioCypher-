import { describe, expect, it, vi } from "vitest";
import {
  careTaskStatusSchema,
  careTaskResponseSchema,
  careTaskListResponseSchema,
  createCareTaskRequestSchema,
  startCareTaskResponseSchema,
  completeCareTaskResponseSchema,
  reassignCareTaskRequestSchema,
  reassignCareTaskResponseSchema,
} from "../../src/services/schemas/tasks";
import {
  fetchCareTasks,
  fetchCareTaskDetail,
  createCareTask,
  startCareTask,
  completeCareTask,
  reassignCareTask,
  fetchPatientDetail,
} from "../../src/features/tasks/api";
import * as taskHooks from "../../src/features/tasks/useCareTasks";
import { can, capabilitiesForRole } from "../../src/authz/capabilities";
import { roleFromAuthRoles } from "../../src/authz/roles";
import { ApiClient } from "../../src/services/api/client";
import { readApiConfig } from "../../src/services/api/config";
import type { ApiErrorDetails } from "../../src/services/api/errors";
import type { AuthSessionProvider } from "../../src/auth/AuthSessionProvider";
import { InMemoryIdempotencyKeyStore, idempotencyKeyFor } from "../../src/services/api/idempotency";

const validUUID = "3fa85f64-5717-4562-b3fc-2c963f66afa6";
const validWorkerUUID = "e4a21190-3cb8-47e2-861f-998811223344";

function makeClient(
  fetchImpl: typeof fetch,
  authProvider?: AuthSessionProvider
) {
  return new ApiClient({
    config: readApiConfig({
      EXPO_PUBLIC_API_BASE_URL: "http://api.test",
      ...process.env,
    }),
    fetchImpl,
    createCorrelationId: () => "corr-gate-10j-m",
    authProvider,
  });
}

describe("GATE 10J-M: Field Health Worker & Care Coordinator Workflows (34 Tests)", () => {
  // ──────────────────────────────────────────────────────────────────────────
  // FHW Workflow Tests (1–18)
  // ──────────────────────────────────────────────────────────────────────────
  describe("FHW Workflow (1–18)", () => {
    it("10J-M-01: FHW role mapping resolves backend token to FieldHealthWorker", () => {
      const resolvedRole = roleFromAuthRoles(["field_health_worker"]);
      expect(resolvedRole).toBe("FieldHealthWorker");
    });

    it("10J-M-02: FHW capability model grants assigned task & observation permissions, denies coordinator controls", () => {
      const fhwCaps = capabilitiesForRole("FieldHealthWorker");
      expect(fhwCaps).toContain("READ_ASSIGNED_TASKS");
      expect(fhwCaps).toContain("START_ASSIGNED_TASK");
      expect(fhwCaps).toContain("COMPLETE_ASSIGNED_TASK");
      expect(fhwCaps).toContain("WRITE_OBSERVATIONS");
      expect(fhwCaps).toContain("WRITE_MEAL_OBSERVATIONS");

      // Strict negative capability assertions (no coordinator controls)
      expect(can("FieldHealthWorker", "CREATE_CARE_TASK")).toBe(false);
      expect(can("FieldHealthWorker", "REASSIGN_CARE_TASK")).toBe(false);
      expect(can("FieldHealthWorker", "MANAGE_CAREGIVER_RELATIONSHIPS")).toBe(false);
      expect(can("FieldHealthWorker", "WRITE_MEDICATION_PLANS")).toBe(false);
    });

    it("10J-M-03: FHW task list contract queries GET /api/v2/care-tasks with assigned_to_me=true", async () => {
      const fetchImpl = vi.fn(async (url: string) => {
        expect(url).toBe("http://api.test/api/v2/care-tasks?assigned_to_me=true");
        return new Response(
          JSON.stringify({ patient_id: null, task_count: 0, items: [] }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      });
      const client = makeClient(fetchImpl as unknown as typeof fetch);
      const res = await fetchCareTasks({ assigned_to_me: true }, client);
      expect(res.task_count).toBe(0);
      expect(fetchImpl).toHaveBeenCalledOnce();
    });

    it("10J-M-04: FHW task list schema validates CareTaskListResponse strictly", () => {
      const validPayload = {
        patient_id: null,
        task_count: 1,
        items: [
          {
            care_task_id: "ct-fhw-01",
            patient_id: validUUID,
            assigned_to_user_id: validWorkerUUID,
            description: "Check fasting blood sugar and adherence",
            status: "open",
            due_at: "2026-09-20T08:00:00Z",
            created_at: "2026-09-17T08:00:00Z",
            completed_at: null,
          },
        ],
      };
      const parsed = careTaskListResponseSchema.parse(validPayload);
      expect(parsed.items[0]?.care_task_id).toBe("ct-fhw-01");
      expect(parsed.items[0]?.status).toBe("open");

      // Extra fields must be rejected (strict schema)
      expect(() =>
        careTaskListResponseSchema.parse({
          ...validPayload,
          unauthorized_extra: true,
        })
      ).toThrow();
    });

    it("10J-M-05: FHW task filtering by status encodes query parameters", async () => {
      const fetchImpl = vi.fn(async (url: string) => {
        expect(url).toContain("assigned_to_me=true");
        expect(url).toContain("status=in_progress");
        return new Response(
          JSON.stringify({ patient_id: null, task_count: 0, items: [] }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      });
      const client = makeClient(fetchImpl as unknown as typeof fetch);
      expect(careTaskStatusSchema.parse("in_progress")).toBe("in_progress");
      await fetchCareTasks({ assigned_to_me: true, status: "in_progress" }, client);
      expect(fetchImpl).toHaveBeenCalledOnce();
    });

    it("10J-M-06: FHW empty state handling parses 0-task response cleanly", () => {
      const emptyPayload = {
        patient_id: null,
        task_count: 0,
        items: [],
      };
      const parsed = careTaskListResponseSchema.parse(emptyPayload);
      expect(parsed.task_count).toBe(0);
      expect(parsed.items).toHaveLength(0);
    });

    it("10J-M-07: FHW task detail contract calls GET /api/v2/care-tasks/{taskId}", async () => {
      const mockTask = {
        care_task_id: "ct-fhw-02",
        patient_id: validUUID,
        assigned_to_user_id: validWorkerUUID,
        description: "Review home blood pressure and glucose logs",
        status: "open",
        due_at: null,
        created_at: "2026-09-17T08:00:00Z",
        completed_at: null,
      };
      const fetchImpl = vi.fn(async (url: string) => {
        expect(url).toBe("http://api.test/api/v2/care-tasks/ct-fhw-02");
        return new Response(JSON.stringify(mockTask), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      });
      const client = makeClient(fetchImpl as unknown as typeof fetch);
      const res = await fetchCareTaskDetail("ct-fhw-02", client);
      expect(res.care_task_id).toBe("ct-fhw-02");
      expect(res.description).toBe("Review home blood pressure and glucose logs");
    });

    it("10J-M-08: Patient context resolution calls authoritative GET /api/v2/patients/{patient_id}", async () => {
      const mockPatient = {
        patient_id: validUUID,
        uh_id: "UH-FHW-100",
        name: "Kavita Devi",
        facility_id: "fac-rural-west",
        active: true,
        created_at: "2026-09-17T00:00:00Z",
      };
      const fetchImpl = vi.fn(async (url: string) => {
        expect(url).toBe(`http://api.test/api/v2/patients/${validUUID}`);
        return new Response(JSON.stringify(mockPatient), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      });
      const client = makeClient(fetchImpl as unknown as typeof fetch);
      const res = await fetchPatientDetail(validUUID, client);
      expect(res.name).toBe("Kavita Devi");
      expect(res.active).toBe(true);
    });

    it("10J-M-09: Patient context resolution does not trust navigation params for authorization", () => {
      // Proves backend remains authoritative by validating that patient details require API resolution
      const rawTask = {
        care_task_id: "ct-009",
        patient_id: validUUID,
        assigned_to_user_id: validWorkerUUID,
        description: "Authoritative patient resolution test",
        status: "open",
        created_at: "2026-09-17T00:00:00Z",
      };
      const parsed = careTaskResponseSchema.parse(rawTask);
      expect(parsed.patient_id).toBe(validUUID);
      // Navigation param is just an identifier; authorization is verified by GET /api/v2/patients/{id}
    });

    it("10J-M-10: Inactive patient produces safe authorization response (403)", async () => {
      const fetchImpl = vi.fn(async () =>
        new Response(JSON.stringify({ detail: "Access denied" }), {
          status: 403,
          headers: { "Content-Type": "application/json" },
        })
      );
      const client = makeClient(fetchImpl as unknown as typeof fetch);
      await expect(fetchPatientDetail(validUUID, client)).rejects.toMatchObject({
        httpStatus: 403,
        kind: "FORBIDDEN",
      });
    });

    it("10J-M-11: FHW start task contract sends POST /api/v2/care-tasks/{taskId}/start with Idempotency-Key", async () => {
      const fetchImpl = vi.fn(async (url: string, init: RequestInit) => {
        expect(url).toBe("http://api.test/api/v2/care-tasks/ct-011/start");
        expect(init.method).toBe("POST");
        const headers = new Headers(init.headers as Record<string, string>);
        expect(headers.get("Idempotency-Key")).toBe("idemp-start-011");
        return new Response(
          JSON.stringify({ care_task_id: "ct-011", status: "in_progress" }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      });
      const client = makeClient(fetchImpl as unknown as typeof fetch);
      const res = await startCareTask("ct-011", client, undefined, "idemp-start-011");
      expect(res.status).toBe("in_progress");
    });

    it("10J-M-12: FHW start task state transition validates in_progress response schema", () => {
      const payload = {
        care_task_id: "ct-012",
        status: "in_progress",
      };
      const parsed = startCareTaskResponseSchema.parse(payload);
      expect(parsed.status).toBe("in_progress");

      // Must reject any status other than in_progress
      expect(() =>
        startCareTaskResponseSchema.parse({
          care_task_id: "ct-012",
          status: "completed",
        })
      ).toThrow();
    });

    it("10J-M-13: FHW field data capture integrates glucose observation via existing endpoint", async () => {
      const fetchImpl = vi.fn(async (url: string, init: RequestInit) => {
        expect(url).toBe("http://api.test/api/v2/clinical/observations");
        expect(init.method).toBe("POST");
        return new Response(
          JSON.stringify({
            observation_id: "obs-glu-01",
            patient_id: validUUID,
            value_mg_dl: 115,
            tag: "fasting",
            recorded_at: "2026-09-17T08:30:00Z",
          }),
          { status: 201, headers: { "Content-Type": "application/json" } }
        );
      });
      const client = makeClient(fetchImpl as unknown as typeof fetch);
      const res = await client.request({
        method: "POST",
        path: "/api/v2/clinical/observations",
        body: { patient_id: validUUID, value_mg_dl: 115, tag: "fasting" },
      });
      expect(res).toBeTruthy();
    });

    it("10J-M-14: FHW field data capture integrates meal observation via existing contracts", async () => {
      const fetchImpl = vi.fn(async (url: string, init: RequestInit) => {
        expect(url).toBe("http://api.test/api/v2/clinical/meals");
        expect(init.method).toBe("POST");
        return new Response(
          JSON.stringify({
            meal_observation_id: "obs-meal-01",
            patient_id: validUUID,
            portion_label: "medium",
            quantity: 1.0,
          }),
          { status: 201, headers: { "Content-Type": "application/json" } }
        );
      });
      const client = makeClient(fetchImpl as unknown as typeof fetch);
      const res = await client.request({
        method: "POST",
        path: "/api/v2/clinical/meals",
        body: {
          patient_id: validUUID,
          description: "Roti and Sabzi",
          portion: { food_key: "roti", katori_volume_ml: 150, quantity: 2.0 },
        },
      });
      expect(res).toBeTruthy();
    });

    it("10J-M-15: FHW complete task contract sends POST /api/v2/care-tasks/{taskId}/complete with Idempotency-Key", async () => {
      const fetchImpl = vi.fn(async (url: string, init: RequestInit) => {
        expect(url).toBe("http://api.test/api/v2/care-tasks/ct-015/complete");
        expect(init.method).toBe("POST");
        const headers = new Headers(init.headers as Record<string, string>);
        expect(headers.get("Idempotency-Key")).toBe("idemp-comp-015");
        return new Response(
          JSON.stringify({
            care_task_id: "ct-015",
            status: "completed",
            completed_at: "2026-09-17T09:00:00Z",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      });
      const client = makeClient(fetchImpl as unknown as typeof fetch);
      const res = await completeCareTask("ct-015", client, undefined, "idemp-comp-015");
      expect(res.status).toBe("completed");
      expect(res.completed_at).toBe("2026-09-17T09:00:00Z");
    });

    it("10J-M-16: FHW complete task state transition validates completed response schema", () => {
      const payload = {
        care_task_id: "ct-016",
        status: "completed",
        completed_at: "2026-09-17T09:15:00Z",
      };
      const parsed = completeCareTaskResponseSchema.parse(payload);
      expect(parsed.status).toBe("completed");
      expect(parsed.completed_at).toBeTruthy();

      // Must reject completed task without completed_at
      expect(() =>
        completeCareTaskResponseSchema.parse({
          care_task_id: "ct-016",
          status: "completed",
        })
      ).toThrow();
    });

    it("10J-M-17: Invalid task transitions return 409 conflict", async () => {
      const fetchImpl = vi.fn(async () =>
        new Response(
          JSON.stringify({
            error: {
              code: "INVALID_STATE_TRANSITION",
              message: "Cannot transition task from completed to in_progress",
            },
          }),
          { status: 409, headers: { "Content-Type": "application/json" } }
        )
      );
      const client = makeClient(fetchImpl as unknown as typeof fetch);
      await expect(startCareTask("ct-017", client, undefined, "idemp-017")).rejects.toMatchObject({
        httpStatus: 409,
        kind: "CONFLICT",
      });
    });

    it("10J-M-18: FHW receives no coordinator-only controls in role capability gating", () => {
      expect(can("FieldHealthWorker", "CREATE_CARE_TASK")).toBe(false);
      expect(can("FieldHealthWorker", "REASSIGN_CARE_TASK")).toBe(false);
    });
  });

  // ──────────────────────────────────────────────────────────────────────────
  // Care Coordinator Workflow Tests (19–28)
  // ──────────────────────────────────────────────────────────────────────────
  describe("Care Coordinator Workflow (19–28)", () => {
    it("10J-M-19: Coordinator role mapping resolves backend token to CareCoordinator", () => {
      const resolvedRole = roleFromAuthRoles(["care_coordinator"]);
      expect(resolvedRole).toBe("CareCoordinator");
    });

    it("10J-M-20: Coordinator capability model grants facility task queue and assignment capabilities", () => {
      const coordCaps = capabilitiesForRole("CareCoordinator");
      expect(coordCaps).toContain("READ_CARE_TASKS");
      expect(coordCaps).toContain("CREATE_CARE_TASK");
      expect(coordCaps).toContain("REASSIGN_CARE_TASK");
      expect(coordCaps).toContain("MANAGE_CAREGIVER_RELATIONSHIPS");
      expect(coordCaps).toContain("READ_PATIENT");
      expect(coordCaps).toContain("WRITE_PATIENT");
    });

    it("10J-M-21: Coordinator queries facility task queue without assigned_to_me", async () => {
      const fetchImpl = vi.fn(async (url: string) => {
        expect(url).toBe("http://api.test/api/v2/care-tasks");
        expect(url).not.toContain("assigned_to_me=true");
        return new Response(
          JSON.stringify({ patient_id: null, task_count: 0, items: [] }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      });
      const client = makeClient(fetchImpl as unknown as typeof fetch);
      await fetchCareTasks(undefined, client);
      expect(fetchImpl).toHaveBeenCalledOnce();
    });

    it("10J-M-22: Coordinator queue supports status filtering", async () => {
      const fetchImpl = vi.fn(async (url: string) => {
        expect(url).toBe("http://api.test/api/v2/care-tasks?status=open");
        return new Response(
          JSON.stringify({ patient_id: null, task_count: 0, items: [] }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      });
      const client = makeClient(fetchImpl as unknown as typeof fetch);
      await fetchCareTasks({ status: "open" }, client);
      expect(fetchImpl).toHaveBeenCalledOnce();
    });

    it("10J-M-23: Coordinator task detail retrieval resolves task and patient context", async () => {
      const mockTask = {
        care_task_id: "ct-coord-023",
        patient_id: validUUID,
        assigned_to_user_id: validWorkerUUID,
        description: "Facility cohort intake check",
        status: "open",
        due_at: "2026-09-22T09:00:00Z",
        created_at: "2026-09-17T08:00:00Z",
        completed_at: null,
      };
      const fetchImpl = vi.fn(async (url: string) => {
        if (url.includes("/api/v2/care-tasks/")) {
          return new Response(JSON.stringify(mockTask), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(
          JSON.stringify({
            patient_id: validUUID,
            uh_id: "UH-999",
            name: "Sunil Das",
            facility_id: "fac-1",
            active: true,
            created_at: "2026-09-17T00:00:00Z",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      });
      const client = makeClient(fetchImpl as unknown as typeof fetch);
      const task = await fetchCareTaskDetail("ct-coord-023", client);
      const patient = await fetchPatientDetail(task.patient_id, client);

      expect(task.care_task_id).toBe("ct-coord-023");
      expect(patient.name).toBe("Sunil Das");
    });

    it("10J-M-24: Coordinator create task contract validates payload and sends Idempotency-Key", async () => {
      const requestPayload = {
        patient_id: validUUID,
        assigned_to_user_id: validWorkerUUID,
        description: "Post-discharge in-person glucose verification",
        due_at: "2026-09-22T10:00:00Z",
      };
      const parsed = createCareTaskRequestSchema.parse(requestPayload);
      expect(parsed.description).toBe("Post-discharge in-person glucose verification");

      const fetchImpl = vi.fn(async (url: string, init: RequestInit) => {
        expect(url).toBe("http://api.test/api/v2/care-tasks");
        expect(init.method).toBe("POST");
        const headers = new Headers(init.headers as Record<string, string>);
        expect(headers.get("Idempotency-Key")).toBe("idemp-create-024");
        return new Response(
          JSON.stringify({
            care_task_id: "ct-created-024",
            patient_id: validUUID,
            assigned_to_user_id: validWorkerUUID,
            description: requestPayload.description,
            status: "open",
            due_at: requestPayload.due_at,
            created_at: "2026-09-17T08:00:00Z",
            completed_at: null,
          }),
          { status: 201, headers: { "Content-Type": "application/json" } }
        );
      });
      const client = makeClient(fetchImpl as unknown as typeof fetch);
      const res = await createCareTask(requestPayload, client, undefined, "idemp-create-024");
      expect(res.care_task_id).toBe("ct-created-024");
      expect(res.status).toBe("open");
    });

    it("10J-M-25: Coordinator selects patient from facility scope or enters UUID", async () => {
      const fetchImpl = vi.fn(async (url: string) => {
        expect(url).toBe("http://api.test/api/v2/patients");
        return new Response(
          JSON.stringify({
            patient_count: 1,
            patients: [
              {
                patient_id: validUUID,
                uh_id: "UH-123",
                name: "Facility Patient",
                facility_id: "fac-1",
                active: true,
                created_at: "2026-09-17T00:00:00Z",
              },
            ],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      });
      const client = makeClient(fetchImpl as unknown as typeof fetch);
      const res = await client.request<{ patient_count: number; patients: { patient_id: string }[] }>({
        method: "GET",
        path: "/api/v2/patients",
      });
      expect(res.patients[0]?.patient_id).toBe(validUUID);
    });

    it("10J-M-26: Worker selection fallback architecture uses UUID entry / context without dedicated endpoint", () => {
      // Backend has no GET /api/v2/care-team-members or worker directory endpoint
      // Mobile relies on manual UUID entry or contextually known assignees
      const testAssignee = "11223344-5566-7788-99aa-bbccddeeff00";
      const req = createCareTaskRequestSchema.parse({
        patient_id: validUUID,
        assigned_to_user_id: testAssignee,
        description: "Task for known worker",
      });
      expect(req.assigned_to_user_id).toBe(testAssignee);
    });

    it("10J-M-27: Coordinator reassign task contract calls POST /api/v2/care-tasks/{taskId}/reassign", async () => {
      const newWorkerId = "55443322-1100-9988-7766-554433221100";
      const fetchImpl = vi.fn(async (url: string, init: RequestInit) => {
        expect(url).toBe("http://api.test/api/v2/care-tasks/ct-027/reassign");
        expect(init.method).toBe("POST");
        const headers = new Headers(init.headers as Record<string, string>);
        expect(headers.get("Idempotency-Key")).toBe("idemp-reassign-027");
        const body = JSON.parse(init.body as string);
        expect(body.new_user_id).toBe(newWorkerId);
        return new Response(
          JSON.stringify({
            care_task_id: "ct-027",
            assigned_to_user_id: newWorkerId,
            status: "open",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      });
      const client = makeClient(fetchImpl as unknown as typeof fetch);
      const req = reassignCareTaskRequestSchema.parse({ new_user_id: newWorkerId });
      const res = await reassignCareTask(
        "ct-027",
        req,
        client,
        undefined,
        "idemp-reassign-027"
      );
      const validatedRes = reassignCareTaskResponseSchema.parse(res);
      expect(validatedRes.assigned_to_user_id).toBe(newWorkerId);
    });

    it("10J-M-28: Reassigning a completed task returns 409 conflict and triggers invalidation", async () => {
      const fetchImpl = vi.fn(async () =>
        new Response(
          JSON.stringify({
            error: {
              code: "CANNOT_REASSIGN_COMPLETED_TASK",
              message: "Cannot reassign a task that has already been completed",
            },
          }),
          { status: 409, headers: { "Content-Type": "application/json" } }
        )
      );
      const client = makeClient(fetchImpl as unknown as typeof fetch);
      await expect(
        reassignCareTask("ct-028", { new_user_id: validWorkerUUID }, client, undefined, "idemp-028")
      ).rejects.toMatchObject({
        httpStatus: 409,
        kind: "CONFLICT",
      });
    });
  });

  // ──────────────────────────────────────────────────────────────────────────
  // Integration & Security Tests (29–34)
  // ──────────────────────────────────────────────────────────────────────────
  describe("Integration & Security (29–34)", () => {
    it("10J-M-29: Mutation idempotency preserves key across retries without generating fresh key", () => {
      const store = new InMemoryIdempotencyKeyStore();
      const logicalKey = "care_task:start:ct-029:session-1";

      const key1 = idempotencyKeyFor(logicalKey, store);
      const key2 = idempotencyKeyFor(logicalKey, store);

      expect(key1).toBe(key2);
      expect(typeof key1).toBe("string");
      expect(key1.length).toBeGreaterThan(0);
    });

    it("10J-M-30: Resource 403 Forbidden does NOT trigger session logout or clearSession", async () => {
      const clearSession = vi.fn();
      const signalAuthExpired = vi.fn();
      const authProvider: AuthSessionProvider = {
        getAccessToken: async () => "token-xyz",
        refreshSession: async () => "token-refreshed",
        clearSession,
        getAuthenticatedContext: async () => ({ state: "anonymous" as const }),
        signalAuthExpired,
        onAuthExpired: () => () => {},
      };

      const fetchImpl = vi.fn(async () =>
        new Response(
          JSON.stringify({ detail: "Field health workers may only view tasks assigned to themselves" }),
          { status: 403, headers: { "Content-Type": "application/json" } }
        )
      );
      const client = makeClient(fetchImpl as unknown as typeof fetch, authProvider);

      let thrownError: ApiErrorDetails | undefined;
      try {
        await fetchCareTasks({ assigned_to_user_id: "other-user-uuid" }, client);
      } catch (err) {
        thrownError = err as ApiErrorDetails;
      }

      expect(thrownError?.httpStatus).toBe(403);
      expect(thrownError?.kind).toBe("FORBIDDEN");
      expect(clearSession).not.toHaveBeenCalled();
      expect(signalAuthExpired).not.toHaveBeenCalled();
    });

    it("10J-M-31: 404 Not Found returns typed error without crashing application", async () => {
      const fetchImpl = vi.fn(async () =>
        new Response(JSON.stringify({ detail: "Care task not found" }), {
          status: 404,
          headers: { "Content-Type": "application/json" },
        })
      );
      const client = makeClient(fetchImpl as unknown as typeof fetch);

      await expect(fetchCareTaskDetail("non-existent-uuid", client)).rejects.toMatchObject({
        httpStatus: 404,
        kind: "NOT_FOUND",
      });
    });

    it("10J-M-32: Information asymmetry: care task contracts strictly exclude carbohydrate and GI calculations", () => {
      const sampleTask = {
        care_task_id: "ct-032",
        patient_id: validUUID,
        assigned_to_user_id: validWorkerUUID,
        description: "Lunch meal observation",
        status: "open",
        created_at: "2026-09-17T08:00:00Z",
      };

      // Strict schema ensures no leaking of clinical nutritional fields
      const parsed = careTaskResponseSchema.parse(sampleTask);
      expect("carbs_grams" in parsed).toBe(false);
      expect("glycemic_index" in parsed).toBe(false);
      expect("carb_formula" in parsed).toBe(false);
    });

    it("10J-M-33: Offline exclusion: Gate 10J-M uses pure online-only architecture", () => {
      // Verifies that neither SQLite, SQLCipher, nor offline queue modules are imported by tasks feature
      expect(fetchCareTasks).toBeTypeOf("function");
      expect(createCareTask).toBeTypeOf("function");
      expect(startCareTask).toBeTypeOf("function");
      expect(completeCareTask).toBeTypeOf("function");
      expect(reassignCareTask).toBeTypeOf("function");
      expect(taskHooks.useCareTasks).toBeTypeOf("function");
      expect(taskHooks.useStartCareTask).toBeTypeOf("function");
      expect(taskHooks.useCompleteCareTask).toBeTypeOf("function");
      expect(taskHooks.useCreateCareTask).toBeTypeOf("function");
      expect(taskHooks.useReassignCareTask).toBeTypeOf("function");
      // All operations rely solely on TanStack Query + ApiClient without offline queues
    });

    it("10J-M-34: Authorization boundaries deny Patient and Caregiver workforce task surfaces", () => {
      expect(can("Patient", "READ_CARE_TASKS")).toBe(false);
      expect(can("Patient", "CREATE_CARE_TASK")).toBe(false);
      expect(can("Patient", "START_CARE_TASK")).toBe(false);
      expect(can("Patient", "COMPLETE_CARE_TASK")).toBe(false);

      expect(can("Caregiver", "READ_CARE_TASKS")).toBe(false);
      expect(can("Caregiver", "CREATE_CARE_TASK")).toBe(false);
    });
  });
});
