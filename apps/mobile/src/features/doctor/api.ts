import { apiClient, type ApiClient } from "../../services/api/client";
import { aiEndpoints } from "../../services/api/endpoints/ai";
import { clinicalEndpoints } from "../../services/api/endpoints/clinical";
import { medicationEndpoints } from "../../services/api/endpoints/medication";
import { patientsEndpoints } from "../../services/api/endpoints/patients";
import {
  clinicianObservationFeedSchema,
  type ClinicianObservationFeedResponse,
} from "../../services/schemas/clinical";
import type {
  AIArtifactListResponse,
  AIArtifactResponse,
  ReviewAIArtifactRequest,
  ReviewAIArtifactResponse,
} from "../../services/schemas/ai";
import type {
  CreateMedicationPlanRequest,
  CreateMedicationPlanResponse,
  MedicationPlanListResponse,
  MedicationPlanResponse,
} from "../../services/schemas/medication";
import type {
  PatientListResponse,
  PatientSummaryResponse,
} from "../../services/schemas/patients";
import type {
  CareTaskListResponse,
  CareTaskResponse,
  CreateCareTaskRequest,
  StartCareTaskResponse,
  CompleteCareTaskResponse,
} from "../../services/schemas/tasks";
import { tasksEndpoints, buildCareTasksPath } from "../../services/api/endpoints/tasks";
import type { NotificationListResponse } from "../../services/schemas/notifications";
import { notificationsEndpoints, buildNotificationsPath } from "../../services/api/endpoints/notifications";

export type ClinicalDocumentItem = {
  id: string;
  patient_id: string;
  kind: string;
  filename: string;
  mime_type: string;
  file_size_bytes: number;
  created_at: string;
  download_url?: string | null;
};

export type ClinicalInsightsResponse = {
  patient_id: string;
  patient_name: string;
  provider: string;
  metrics: {
    total_readings: number;
    mean_glucose_mg_dl: number | null;
    standard_deviation_mg_dl: number | null;
    coefficient_of_variation_pct: number | null;
    time_in_range_pct: number | null;
    time_below_range_pct: number | null;
    time_above_range_pct: number | null;
    estimated_hba1c_pct: number | null;
    glucose_management_indicator_pct: number | null;
    dawn_phenomenon_suspected: boolean;
    variability_category: string;
    clinical_summary_note: string;
  };
  recent_meals: Array<{
    description: string;
    recorded_at: string | null;
    analysis: number;
  }>;
  active_medications: Array<{
    medication: string;
    instruction: string | null;
    active: boolean;
  }>;
};

/**
 * Doctor / P.L.A.T.E. reads and mutations (Gate 10F-B contracts → Gate 10F-M).
 *
 * Every response is validated against the sealed DTO mirror. Clinician-only
 * fields (carbs_grams / glycemic_index) are carried ONLY by the clinician
 * feed schema — patient/caregiver surfaces use distinct schemas and never
 * share these types. The backend remains the authorization authority; these
 * functions add no secondary auth.
 */

export async function fetchReviewQueue(
  client: ApiClient = apiClient,
  token?: string
): Promise<AIArtifactListResponse> {
  return client.request<AIArtifactListResponse>({
    method: aiEndpoints.queue.method,
    path: aiEndpoints.queue.path,
    schema: aiEndpoints.queue.responseSchema,
    token,
  });
}

export async function fetchArtifactDetail(
  artifactId: string,
  client: ApiClient = apiClient,
  token?: string
): Promise<AIArtifactResponse> {
  return client.request<AIArtifactResponse>({
    method: aiEndpoints.detail.method,
    path: aiEndpoints.detail.path(artifactId),
    schema: aiEndpoints.detail.responseSchema,
    token,
  });
}

export async function submitArtifactReview(
  artifactId: string,
  request: ReviewAIArtifactRequest,
  idempotencyKey: string,
  client: ApiClient = apiClient,
  token?: string
): Promise<ReviewAIArtifactResponse> {
  return client.request<ReviewAIArtifactResponse>({
    method: aiEndpoints.review.method,
    path: aiEndpoints.review.path(artifactId),
    body: request,
    idempotencyKey,
    schema: aiEndpoints.review.responseSchema,
    token,
  });
}

export async function fetchPatients(
  client: ApiClient = apiClient,
  token?: string
): Promise<PatientListResponse> {
  return client.request<PatientListResponse>({
    method: patientsEndpoints.list.method,
    path: patientsEndpoints.list.path,
    schema: patientsEndpoints.list.responseSchema,
    token,
  });
}

export async function fetchPatientDetail(
  patientId: string,
  client: ApiClient = apiClient,
  token?: string
): Promise<PatientSummaryResponse> {
  return client.request<PatientSummaryResponse>({
    method: patientsEndpoints.detail.method,
    path: patientsEndpoints.detail.path(patientId),
    schema: patientsEndpoints.detail.responseSchema,
    token,
  });
}

export async function fetchClinicianFeed(
  patientId: string,
  limit: number = 50,
  client: ApiClient = apiClient,
  token?: string
): Promise<ClinicianObservationFeedResponse> {
  const query = `?patient_id=${encodeURIComponent(patientId)}&limit=${limit}`;
  const response = await client.request<ClinicianObservationFeedResponse>({
    method: clinicalEndpoints.clinicianFeed.method,
    path: `${clinicalEndpoints.clinicianFeed.path}${query}`,
    schema: clinicalEndpoints.clinicianFeed.responseSchema,
    token,
  });
  return assertClinicianSafeFeed(response);
}

export async function fetchMedicationPlans(
  client: ApiClient = apiClient,
  token?: string
): Promise<MedicationPlanListResponse> {
  return client.request<MedicationPlanListResponse>({
    method: medicationEndpoints.plans.method,
    path: medicationEndpoints.plans.path,
    schema: medicationEndpoints.plans.responseSchema,
    token,
  });
}

export async function fetchMedicationPlan(
  planId: string,
  client: ApiClient = apiClient,
  token?: string
): Promise<MedicationPlanResponse> {
  return client.request<MedicationPlanResponse>({
    method: medicationEndpoints.planDetail.method,
    path: medicationEndpoints.planDetail.path(planId),
    schema: medicationEndpoints.planDetail.responseSchema,
    token,
  });
}

export async function createMedicationPlan(
  request: CreateMedicationPlanRequest,
  idempotencyKey: string,
  client: ApiClient = apiClient,
  token?: string
): Promise<CreateMedicationPlanResponse> {
  return client.request<CreateMedicationPlanResponse>({
    method: medicationEndpoints.createPlan.method,
    path: medicationEndpoints.createPlan.path,
    body: request,
    idempotencyKey,
    schema: medicationEndpoints.createPlan.responseSchema,
    token,
  });
}

/**
 * Defense-in-depth for the CLINICIAN feed (Gate 10A §13 asymmetry invariant
 * applied to the Doctor direction). The strict Zod schema already enforces the
 * sealed DTO; this guard additionally refuses any feed item that does not carry
 * clinician lifecycle markers (observation_id, confirmation), so a patient-DTO
 * item can never be mistaken for clinician output and rendered.
 */
export function isClinicianObservation(item: unknown): boolean {
  if (typeof item !== "object" || item === null) return false;
  const record = item as Record<string, unknown>;
  return "observation_id" in record && "confirmation" in record;
}

export function assertClinicianSafeFeed(
  response: ClinicianObservationFeedResponse
): ClinicianObservationFeedResponse {
  clinicianObservationFeedSchema.parse(response);
  if (!response.items.every(isClinicianObservation)) {
    throw new Error("Clinician feed contained non-clinician observation items.");
  }
  return response;
}

export async function generateClinicalReport(
  request: { patient_id: string; report_type?: string; format?: string },
  idempotencyKey: string,
  client: ApiClient = apiClient,
  token?: string
): Promise<ClinicalDocumentItem> {
  return client.request<ClinicalDocumentItem>({
    method: "POST",
    path: "/api/v2/clinical/reports/generate",
    body: {
      patient_id: request.patient_id,
      report_type: request.report_type ?? "clinical_summary",
      format: request.format ?? "pdf",
    },
    idempotencyKey,
    token,
  });
}

export async function fetchPatientDocuments(
  patientId: string,
  client: ApiClient = apiClient,
  token?: string
): Promise<ClinicalDocumentItem[]> {
  const res = await client.request<{ total?: number; count?: number; items: ClinicalDocumentItem[] }>({
    method: "GET",
    path: `/api/v2/clinical/patients/${encodeURIComponent(patientId)}/documents`,
    token,
  });
  return res.items || [];
}

export async function uploadPatientDocument(
  patientId: string,
  request: { filename: string; mime_type: string; content_base64: string; kind?: string },
  idempotencyKey: string,
  client: ApiClient = apiClient,
  token?: string
): Promise<ClinicalDocumentItem> {
  return client.request<ClinicalDocumentItem>({
    method: "POST",
    path: `/api/v2/clinical/patients/${encodeURIComponent(patientId)}/documents/upload`,
    body: {
      filename: request.filename,
      mime_type: request.mime_type,
      content_base64: request.content_base64,
      kind: request.kind ?? "chart_image",
    },
    idempotencyKey,
    token,
  });
}

export async function fetchClinicalInsights(
  patientId: string,
  client: ApiClient = apiClient,
  token?: string
): Promise<ClinicalInsightsResponse> {
  return client.request<ClinicalInsightsResponse>({
    method: "GET",
    path: `/api/v2/ai/clinical-insights/${encodeURIComponent(patientId)}`,
    token,
  });
}

export async function fetchCareTasks(
  patientId?: string,
  client: ApiClient = apiClient,
  token?: string
): Promise<CareTaskListResponse> {
  const path = buildCareTasksPath(patientId ? { patient_id: patientId } : undefined);
  return client.request<CareTaskListResponse>({
    method: tasksEndpoints.list.method,
    path,
    schema: tasksEndpoints.list.responseSchema,
    token,
  });
}

export async function createCareTask(
  request: CreateCareTaskRequest,
  idempotencyKey: string,
  client: ApiClient = apiClient,
  token?: string
): Promise<CareTaskResponse> {
  return client.request<CareTaskResponse>({
    method: tasksEndpoints.create.method,
    path: tasksEndpoints.create.path,
    body: request,
    idempotencyKey,
    schema: tasksEndpoints.create.responseSchema,
    token,
  });
}

export async function startCareTask(
  taskId: string,
  idempotencyKey: string,
  client: ApiClient = apiClient,
  token?: string
): Promise<StartCareTaskResponse> {
  return client.request<StartCareTaskResponse>({
    method: tasksEndpoints.start.method,
    path: tasksEndpoints.start.path(taskId),
    idempotencyKey,
    schema: tasksEndpoints.start.responseSchema,
    token,
  });
}

export async function completeCareTask(
  taskId: string,
  idempotencyKey: string,
  client: ApiClient = apiClient,
  token?: string
): Promise<CompleteCareTaskResponse> {
  return client.request<CompleteCareTaskResponse>({
    method: tasksEndpoints.complete.method,
    path: tasksEndpoints.complete.path(taskId),
    idempotencyKey,
    schema: tasksEndpoints.complete.responseSchema,
    token,
  });
}

export async function fetchDoctorNotifications(
  patientId?: string,
  client: ApiClient = apiClient,
  token?: string
): Promise<NotificationListResponse> {
  const path = buildNotificationsPath(patientId ? { patient_id: patientId } : undefined);
  return client.request<NotificationListResponse>({
    method: notificationsEndpoints.list.method,
    path,
    schema: notificationsEndpoints.list.responseSchema,
    token,
  });
}