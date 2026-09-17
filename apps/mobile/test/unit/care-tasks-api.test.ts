import { describe, expect, it, vi } from "vitest";
import {
  fetchCareTasks,
  fetchCareTaskDetail,
  createCareTask,
  startCareTask,
  completeCareTask,
  reassignCareTask,
  fetchPatientDetail,
} from "../../src/features/tasks/api";
import { ApiClient } from "../../src/services/api/client";
import { readApiConfig } from "../../src/services/api/config";
import type { ApiErrorDetails } from "../../src/services/api/errors";
import type { AuthSessionProvider } from "../../src/auth/AuthSessionProvider";

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
    createCorrelationId: () => "corr-task-test-001",
    authProvider,
  });
}

describe("Gate 10J-M Care Tasks API Integration", () => {
  describe("fetchCareTasks", () => {
    it("calls GET /api/v2/care-tasks without query params", async () => {
      const mockResponse = {
        patient_id: null,
        task_count: 0,
        items: [],
      };

      const fetchImpl = vi.fn(async (url: string) => {
        expect(url).toBe("http://api.test/api/v2/care-tasks");
        return new Response(JSON.stringify(mockResponse), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      });

      const client = makeClient(fetchImpl as unknown as typeof fetch);
      const res = await fetchCareTasks(undefined, client, "test-token");
      expect(res.task_count).toBe(0);
      expect(res.items).toEqual([]);

      const [, reqInit] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
      const headers = new Headers(reqInit.headers as Record<string, string>);
      expect(headers.get("Authorization")).toBe("Bearer test-token");
      expect(headers.get("X-Correlation-ID")).toBe("corr-task-test-001");
    });

    it("sends assigned_to_me=true when querying for FHW", async () => {
      const mockResponse = {
        patient_id: null,
        task_count: 1,
        items: [
          {
            care_task_id: "ct-001",
            patient_id: validUUID,
            assigned_to_user_id: validWorkerUUID,
            description: "Check glucose",
            status: "open",
            due_at: null,
            created_at: "2026-09-17T08:00:00Z",
            completed_at: null,
          },
        ],
      };

      const fetchImpl = vi.fn(async (url: string) => {
        expect(url).toContain("assigned_to_me=true");
        return new Response(JSON.stringify(mockResponse), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      });

      const client = makeClient(fetchImpl as unknown as typeof fetch);
      const res = await fetchCareTasks({ assigned_to_me: true }, client);
      expect(res.task_count).toBe(1);
      expect(res.items[0]?.care_task_id).toBe("ct-001");
    });

    it("encodes status and patient_id filters", async () => {
      const fetchImpl = vi.fn(async (url: string) => {
        expect(url).toContain("status=in_progress");
        expect(url).toContain(`patient_id=${validUUID}`);
        return new Response(
          JSON.stringify({ patient_id: validUUID, task_count: 0, items: [] }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      });

      const client = makeClient(fetchImpl as unknown as typeof fetch);
      await fetchCareTasks({ status: "in_progress", patient_id: validUUID }, client);
      expect(fetchImpl).toHaveBeenCalledOnce();
    });
  });

  describe("fetchCareTaskDetail", () => {
    it("calls GET /api/v2/care-tasks/{taskId}", async () => {
      const mockTask = {
        care_task_id: "ct-detail-123",
        patient_id: validUUID,
        assigned_to_user_id: validWorkerUUID,
        description: "Review adherence and diet",
        status: "open",
        due_at: "2026-09-19T00:00:00Z",
        created_at: "2026-09-17T08:00:00Z",
        completed_at: null,
      };

      const fetchImpl = vi.fn(async (url: string) => {
        expect(url).toBe("http://api.test/api/v2/care-tasks/ct-detail-123");
        return new Response(JSON.stringify(mockTask), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      });

      const client = makeClient(fetchImpl as unknown as typeof fetch);
      const res = await fetchCareTaskDetail("ct-detail-123", client);
      expect(res.care_task_id).toBe("ct-detail-123");
      expect(res.status).toBe("open");
    });
  });

  describe("createCareTask", () => {
    it("calls POST /api/v2/care-tasks with Idempotency-Key and payload", async () => {
      const mockCreated = {
        care_task_id: "ct-created-01",
        patient_id: validUUID,
        assigned_to_user_id: validWorkerUUID,
        description: "New task for FHW",
        status: "open",
        due_at: "2026-09-20T12:00:00Z",
        created_at: "2026-09-17T08:00:00Z",
        completed_at: null,
      };

      const fetchImpl = vi.fn(async (url: string, init: RequestInit) => {
        expect(url).toBe("http://api.test/api/v2/care-tasks");
        expect(init.method).toBe("POST");
        const headers = new Headers(init.headers as Record<string, string>);
        expect(headers.get("Idempotency-Key")).toBe("idemp-create-001");
        const body = JSON.parse(init.body as string);
        expect(body.description).toBe("New task for FHW");
        expect(body.patient_id).toBe(validUUID);
        expect(body.assigned_to_user_id).toBe(validWorkerUUID);

        return new Response(JSON.stringify(mockCreated), {
          status: 201,
          headers: { "Content-Type": "application/json" },
        });
      });

      const client = makeClient(fetchImpl as unknown as typeof fetch);
      const res = await createCareTask(
        {
          patient_id: validUUID,
          assigned_to_user_id: validWorkerUUID,
          description: "New task for FHW",
          due_at: "2026-09-20T12:00:00Z",
        },
        client,
        "token-123",
        "idemp-create-001"
      );

      expect(res.care_task_id).toBe("ct-created-01");
      expect(res.status).toBe("open");
    });
  });

  describe("startCareTask", () => {
    it("calls POST /api/v2/care-tasks/{taskId}/start with Idempotency-Key", async () => {
      const mockStarted = {
        care_task_id: "ct-001",
        status: "in_progress",
      };

      const fetchImpl = vi.fn(async (url: string, init: RequestInit) => {
        expect(url).toBe("http://api.test/api/v2/care-tasks/ct-001/start");
        expect(init.method).toBe("POST");
        const headers = new Headers(init.headers as Record<string, string>);
        expect(headers.get("Idempotency-Key")).toBe("idemp-start-001");

        return new Response(JSON.stringify(mockStarted), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      });

      const client = makeClient(fetchImpl as unknown as typeof fetch);
      const res = await startCareTask("ct-001", client, "token-123", "idemp-start-001");
      expect(res.care_task_id).toBe("ct-001");
      expect(res.status).toBe("in_progress");
    });
  });

  describe("completeCareTask", () => {
    it("calls POST /api/v2/care-tasks/{taskId}/complete with Idempotency-Key", async () => {
      const mockCompleted = {
        care_task_id: "ct-001",
        status: "completed",
        completed_at: "2026-09-17T12:30:00Z",
      };

      const fetchImpl = vi.fn(async (url: string, init: RequestInit) => {
        expect(url).toBe("http://api.test/api/v2/care-tasks/ct-001/complete");
        expect(init.method).toBe("POST");
        const headers = new Headers(init.headers as Record<string, string>);
        expect(headers.get("Idempotency-Key")).toBe("idemp-complete-001");

        return new Response(JSON.stringify(mockCompleted), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      });

      const client = makeClient(fetchImpl as unknown as typeof fetch);
      const res = await completeCareTask("ct-001", client, "token-123", "idemp-complete-001");
      expect(res.care_task_id).toBe("ct-001");
      expect(res.status).toBe("completed");
      expect(res.completed_at).toBe("2026-09-17T12:30:00Z");
    });
  });

  describe("reassignCareTask", () => {
    it("calls POST /api/v2/care-tasks/{taskId}/reassign with Idempotency-Key", async () => {
      const mockReassigned = {
        care_task_id: "ct-001",
        assigned_to_user_id: validWorkerUUID,
        status: "open",
      };

      const fetchImpl = vi.fn(async (url: string, init: RequestInit) => {
        expect(url).toBe("http://api.test/api/v2/care-tasks/ct-001/reassign");
        expect(init.method).toBe("POST");
        const headers = new Headers(init.headers as Record<string, string>);
        expect(headers.get("Idempotency-Key")).toBe("idemp-reassign-001");
        const body = JSON.parse(init.body as string);
        expect(body.new_user_id).toBe(validWorkerUUID);

        return new Response(JSON.stringify(mockReassigned), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      });

      const client = makeClient(fetchImpl as unknown as typeof fetch);
      const res = await reassignCareTask(
        "ct-001",
        { new_user_id: validWorkerUUID },
        client,
        "token-123",
        "idemp-reassign-001"
      );

      expect(res.care_task_id).toBe("ct-001");
      expect(res.assigned_to_user_id).toBe(validWorkerUUID);
    });
  });

  describe("fetchPatientDetail", () => {
    it("calls GET /api/v2/patients/{patientId}", async () => {
      const mockPatient = {
        patient_id: validUUID,
        uh_id: "UH-112233",
        name: "Devi Sharma",
        facility_id: "fac-city-east",
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
      expect(res.patient_id).toBe(validUUID);
      expect(res.name).toBe("Devi Sharma");
    });
  });

  describe("Centralized Error Handling & Security", () => {
    it("403 Forbidden does NOT trigger session logout or clearSession", async () => {
      const clearSession = vi.fn();
      const signalAuthExpired = vi.fn();
      const authProvider: AuthSessionProvider = {
        getAccessToken: async () => "tok-initial",
        refreshSession: async () => "refreshed-tok",
        clearSession,
        getAuthenticatedContext: async () => ({ state: "anonymous" as const }),
        signalAuthExpired,
        onAuthExpired: () => () => {},
      };

      const fetchImpl = vi.fn(async () =>
        new Response(JSON.stringify({ detail: "Forbidden: insufficient role capability" }), {
          status: 403,
        })
      );

      const client = makeClient(fetchImpl as unknown as typeof fetch, authProvider);

      let thrown: ApiErrorDetails | undefined;
      try {
        await fetchCareTasks({ assigned_to_me: true }, client);
      } catch (err) {
        thrown = err as ApiErrorDetails;
      }

      expect(thrown?.httpStatus).toBe(403);
      expect(thrown?.kind).toBe("FORBIDDEN");
      expect(clearSession).not.toHaveBeenCalled();
      expect(signalAuthExpired).not.toHaveBeenCalled();
    });

    it("409 Conflict preserves error details for cache invalidation handling", async () => {
      const fetchImpl = vi.fn(async () =>
        new Response(
          JSON.stringify({
            error: {
              code: "TASK_ALREADY_COMPLETED",
              message: "Task has already been completed by another worker",
            },
          }),
          { status: 409, headers: { "Content-Type": "application/json" } }
        )
      );

      const client = makeClient(fetchImpl as unknown as typeof fetch);

      await expect(
        completeCareTask("ct-001", client, "token-123", "idemp-001")
      ).rejects.toMatchObject({
        httpStatus: 409,
        message: expect.stringContaining("Task has already been completed"),
      });
    });

    it("404 Not Found returns proper error details", async () => {
      const fetchImpl = vi.fn(async () =>
        new Response(JSON.stringify({ detail: "Care task not found" }), { status: 404 })
      );

      const client = makeClient(fetchImpl as unknown as typeof fetch);

      await expect(fetchCareTaskDetail("non-existent-id", client)).rejects.toMatchObject({
        httpStatus: 404,
      });
    });
  });
});
