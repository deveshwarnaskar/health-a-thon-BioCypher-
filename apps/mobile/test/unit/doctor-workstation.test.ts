import { describe, expect, it, vi } from "vitest";
import { ApiClient } from "../../src/services/api/client";
import { readApiConfig } from "../../src/services/api/config";
import {
  generateClinicalReport,
  fetchPatientDocuments,
  uploadPatientDocument,
  fetchClinicalInsights,
  fetchCareTasks,
  createCareTask,
  startCareTask,
  completeCareTask,
  fetchDoctorNotifications,
} from "../../src/features/doctor/api";
import { doctorKeys } from "../../src/features/doctor/doctorKeys";

function jsonResponse(status: number, body: unknown, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), { status, headers });
}

function makeClient(fetchImpl: typeof fetch) {
  return new ApiClient({
    config: readApiConfig({ EXPO_PUBLIC_API_BASE_URL: "http://api.test", ...process.env }),
    fetchImpl,
  });
}

describe("P.L.A.T.E. Doctor Workstation Endpoints & Contracts", () => {
  describe("Report Generation & Documents", () => {
    it("POSTs to /api/v2/clinical/reports/generate with Idempotency-Key and returns DocumentReferenceResponse", async () => {
      const mockDoc = {
        id: "doc-123",
        patient_id: "p-456",
        kind: "clinical_summary",
        filename: "clinical_summary_p456.pdf",
        mime_type: "application/pdf",
        file_size_bytes: 45200,
        created_at: "2026-09-22T12:00:00Z",
        download_url: "https://minio.test/clinical_summary_p456.pdf?token=abc",
      };

      const fetchImpl = vi.fn(async () => jsonResponse(200, mockDoc));
      const client = makeClient(fetchImpl);

      const res = await generateClinicalReport(
        { patient_id: "p-456", report_type: "clinical_summary", format: "pdf" },
        "idemp-key-rep-1",
        client,
        "tok-doc"
      );

      const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
      expect(String(url)).toBe("http://api.test/api/v2/clinical/reports/generate");
      expect(init.method).toBe("POST");
      expect(new Headers(init.headers as Record<string, string>).get("Idempotency-Key")).toBe(
        "idemp-key-rep-1"
      );
      expect(new Headers(init.headers as Record<string, string>).get("Authorization")).toBe(
        "Bearer tok-doc"
      );
      expect(res.id).toBe("doc-123");
      expect(res.download_url).toBe("https://minio.test/clinical_summary_p456.pdf?token=abc");
    });

    it("fetches patient documents via GET /api/v2/clinical/patients/{id}/documents", async () => {
      const mockDocs = {
        items: [
          {
            id: "doc-1",
            patient_id: "p-1",
            kind: "lab_report",
            filename: "cbc_report.pdf",
            mime_type: "application/pdf",
            file_size_bytes: 12000,
            created_at: "2026-09-21T08:00:00Z",
          },
        ],
      };

      const fetchImpl = vi.fn(async () => jsonResponse(200, mockDocs));
      const client = makeClient(fetchImpl);

      const items = await fetchPatientDocuments("p-1", client);

      const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
      expect(String(url)).toBe("http://api.test/api/v2/clinical/patients/p-1/documents");
      expect(init.method).toBe("GET");
      expect(items.length).toBe(1);
      expect(items[0]!.filename).toBe("cbc_report.pdf");
    });

    it("uploads patient document via POST /api/v2/clinical/patients/{id}/documents/upload with Idempotency-Key", async () => {
      const mockResult = {
        id: "doc-uploaded",
        patient_id: "p-1",
        kind: "chart_image",
        filename: "glucose_trend.png",
        mime_type: "image/png",
        file_size_bytes: 5400,
        created_at: "2026-09-22T10:00:00Z",
      };

      const fetchImpl = vi.fn(async () => jsonResponse(200, mockResult));
      const client = makeClient(fetchImpl);

      const res = await uploadPatientDocument(
        "p-1",
        {
          filename: "glucose_trend.png",
          mime_type: "image/png",
          content_base64: "iVBORw0KGgo=",
          kind: "chart_image",
        },
        "idemp-upload-1",
        client
      );

      const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
      expect(String(url)).toBe("http://api.test/api/v2/clinical/patients/p-1/documents/upload");
      expect(init.method).toBe("POST");
      expect(new Headers(init.headers as Record<string, string>).get("Idempotency-Key")).toBe(
        "idemp-upload-1"
      );
      expect(res.id).toBe("doc-uploaded");
    });
  });

  describe("Clinical AI Insights Endpoint", () => {
    it("fetches comprehensive glycemic insights via GET /api/v2/ai/clinical-insights/{patient_id}", async () => {
      const mockInsights = {
        patient_id: "p-1",
        patient_name: "Aarav Sharma",
        provider: "sarvam_m",
        metrics: {
          total_readings: 28,
          mean_glucose_mg_dl: 132,
          standard_deviation_mg_dl: 22,
          coefficient_of_variation_pct: 16.7,
          time_in_range_pct: 85,
          time_below_range_pct: 3,
          time_above_range_pct: 12,
          estimated_hba1c_pct: 6.2,
          glucose_management_indicator_pct: 6.4,
          dawn_phenomenon_suspected: false,
          variability_category: "Low",
          clinical_summary_note: "Patient maintains adequate time in range with low glycemic variability.",
        },
        recent_meals: [],
        active_medications: [],
      };

      const fetchImpl = vi.fn(async () => jsonResponse(200, mockInsights));
      const client = makeClient(fetchImpl);

      const res = await fetchClinicalInsights("p-1", client);

      const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
      expect(String(url)).toBe("http://api.test/api/v2/ai/clinical-insights/p-1");
      expect(init.method).toBe("GET");
      expect(res.patient_name).toBe("Aarav Sharma");
      expect(res.metrics.time_in_range_pct).toBe(85);
      expect(res.metrics.dawn_phenomenon_suspected).toBe(false);
    });
  });

  describe("Care Tasks Endpoints", () => {
    it("fetches care tasks list via GET /api/v2/care-tasks with optional patient_id", async () => {
      const mockTasks = {
        patient_id: "p-1",
        task_count: 1,
        items: [
          {
            care_task_id: "task-101",
            patient_id: "p-1",
            assigned_to_user_id: "u-1",
            description: "Follow-up fasting SMBG check",
            status: "open",
            created_at: "2026-09-22T08:00:00Z",
          },
        ],
      };

      const fetchImpl = vi.fn(async () => jsonResponse(200, mockTasks));
      const client = makeClient(fetchImpl);

      const res = await fetchCareTasks("p-1", client);

      const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
      expect(String(url)).toBe("http://api.test/api/v2/care-tasks?patient_id=p-1");
      expect(init.method).toBe("GET");
      expect(res.task_count).toBe(1);
      expect(res.items[0]!.description).toBe("Follow-up fasting SMBG check");
    });

    it("creates a care task via POST /api/v2/care-tasks with Idempotency-Key", async () => {
      const mockCreated = {
        care_task_id: "task-new",
        patient_id: "p-1",
        assigned_to_user_id: "u-1",
        description: "Dietary recall audit",
        status: "open",
        created_at: "2026-09-22T09:00:00Z",
      };

      const fetchImpl = vi.fn(async () => jsonResponse(200, mockCreated));
      const client = makeClient(fetchImpl);

      const res = await createCareTask(
        {
          patient_id: "p-1",
          assigned_to_user_id: "u-1",
          description: "Dietary recall audit",
        },
        "key-task-create",
        client
      );

      const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
      expect(String(url)).toBe("http://api.test/api/v2/care-tasks");
      expect(init.method).toBe("POST");
      expect(new Headers(init.headers as Record<string, string>).get("Idempotency-Key")).toBe(
        "key-task-create"
      );
      expect(res.care_task_id).toBe("task-new");
    });

    it("starts a care task via POST /api/v2/care-tasks/{id}/start", async () => {
      const mockStarted = {
        care_task_id: "task-101",
        status: "in_progress",
      };

      const fetchImpl = vi.fn(async () => jsonResponse(200, mockStarted));
      const client = makeClient(fetchImpl);

      const res = await startCareTask("task-101", "key-task-start", client);

      const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
      expect(String(url)).toBe("http://api.test/api/v2/care-tasks/task-101/start");
      expect(init.method).toBe("POST");
      expect(res.status).toBe("in_progress");
    });

    it("completes a care task via POST /api/v2/care-tasks/{id}/complete", async () => {
      const mockCompleted = {
        care_task_id: "task-101",
        status: "completed",
        completed_at: "2026-09-22T10:00:00Z",
      };

      const fetchImpl = vi.fn(async () => jsonResponse(200, mockCompleted));
      const client = makeClient(fetchImpl);

      const res = await completeCareTask("task-101", "key-task-complete", client);

      const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
      expect(String(url)).toBe("http://api.test/api/v2/care-tasks/task-101/complete");
      expect(init.method).toBe("POST");
      expect(res.status).toBe("completed");
    });
  });

  describe("Doctor Notifications Inspection", () => {
    it("fetches notifications via GET /api/v2/notifications", async () => {
      const mockNotifs = {
        total: 2,
        items: [
          {
            id: "notif-1",
            tenant_id: "tenant-default",
            recipient_id: "p-1",
            recipient_phone: "+919876543210",
            notification_type: "alert",
            channel: "WHATSAPP",
            template_name: "morning_glucose_nudge",
            template_params: {},
            status: "delivered",
            created_at: "2026-09-22T06:00:00Z",
            retry_count: 0,
          },
        ],
      };

      const fetchImpl = vi.fn(async () => jsonResponse(200, mockNotifs));
      const client = makeClient(fetchImpl);

      const res = await fetchDoctorNotifications("p-1", client);

      const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
      expect(String(url)).toBe("http://api.test/api/v2/notifications?patient_id=p-1");
      expect(init.method).toBe("GET");
      expect(res.total).toBe(2);
      expect(res.items[0]!.recipient_phone).toBe("+919876543210");
    });
  });

  describe("Doctor Keys Hierarchy & Invalidation Families", () => {
    it("provides stable, partitioned cache keys for all doctor query domains", () => {
      expect(doctorKeys.all).toEqual(["doctor"]);
      expect(doctorKeys.reviewQueue()).toEqual(["doctor", "review", "queue"]);
      expect(doctorKeys.artifact("art-1")).toEqual(["doctor", "review", "artifact", "art-1"]);
      expect(doctorKeys.patients()).toEqual(["doctor", "patients"]);
      expect(doctorKeys.patient("p-1")).toEqual(["doctor", "patients", "p-1"]);
      expect(doctorKeys.clinicianObservations("p-1")).toEqual(["doctor", "observations", "p-1"]);
      expect(doctorKeys.medicationPlans()).toEqual(["doctor", "medication-plans"]);
      expect(doctorKeys.medicationPlans("p-1")).toEqual(["doctor", "medication-plans", "patient", "p-1"]);
      expect(doctorKeys.tasks()).toEqual(["doctor", "tasks"]);
      expect(doctorKeys.tasks("p-1")).toEqual(["doctor", "tasks", "patient", "p-1"]);
      expect(doctorKeys.documents("p-1")).toEqual(["doctor", "documents", "p-1"]);
      expect(doctorKeys.insights("p-1")).toEqual(["doctor", "insights", "p-1"]);
      expect(doctorKeys.notifications("p-1")).toEqual(["doctor", "notifications", "patient", "p-1"]);
    });
  });
});
