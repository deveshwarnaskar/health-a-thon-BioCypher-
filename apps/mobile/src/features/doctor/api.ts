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

export type DocumentDownloadResponse = {
  download_url?: string | null;
  expires_in?: number | null;
  filename: string;
  mime_type: string;
  content_base64?: string | null;
  file_size_bytes?: number | null;
};

export async function fetchDocumentDownload(
  documentId: string,
  options?: { signed_url?: boolean; base64?: boolean },
  client: ApiClient = apiClient,
  token?: string
): Promise<DocumentDownloadResponse> {
  const params: string[] = [];
  if (options?.signed_url) params.push("signed_url=true");
  if (options?.base64) params.push("base64=true");
  const qs = params.length > 0 ? `?${params.join("&")}` : "";
  return client.request<DocumentDownloadResponse>({
    method: "GET",
    path: `/api/v2/clinical/documents/${encodeURIComponent(documentId)}/download${qs}`,
    token,
  });
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

export type PatientClinicalState = {
  patient_summary: {
    patient_id: string;
    name: string;
    uh_id: string;
    phone: string;
    facility_id: string | null;
    care_team: Array<{
      clinician_user_id: string;
      clinician_name: string;
      facility_id: string | null;
    }>;
    active: boolean;
    reporting_window_days: number;
    window_start: string;
    window_end: string;
    clinical_alerts: Array<{
      level: "HIGH" | "MODERATE" | "INFO";
      code: string;
      message: string;
    }>;
  };
  data_quality: {
    window_days: number;
    active_logging_days: number;
    total_valid_readings: number;
    expected_readings: number;
    coverage_ratio: number;
    coverage_pct: number;
    is_adequate_coverage: boolean;
    missing_days_count: number;
    missing_days: string[];
    last_sync: string | null;
    data_sources: string[];
  };
  glycemic_metrics: {
    total_readings: number;
    mean_glucose: number | null;
    median_glucose: number | null;
    min_glucose: number | null;
    max_glucose: number | null;
    standard_deviation: number | null;
    coefficient_of_variation_pct: number | null;
    tir_in_range_pct: number | null;
    tar_above_range_pct: number | null;
    tar_level2_pct: number | null;
    tbr_below_range_pct: number | null;
    tbr_level2_pct: number | null;
    gmi_pct: number | null;
    estimated_a1c_pct: number | null;
    fasting_mean: number | null;
    post_prandial_mean: number | null;
    dawn_phenomenon_suspected: boolean;
    variability_category: string;
    clinical_summary_note: string;
  };
  longitudinal_comparison: {
    period_days: number;
    current_readings_count: number;
    previous_readings_count: number;
    tir_comparison: {
      current_value: number | null;
      previous_value: number | null;
      delta: number | null;
      trend_direction: string;
    };
    mean_comparison: {
      current_value: number | null;
      previous_value: number | null;
      delta: number | null;
      trend_direction: string;
    };
    cv_comparison: {
      current_value: number | null;
      previous_value: number | null;
      delta: number | null;
      trend_direction: string;
    };
    gmi_comparison: {
      current_value: number | null;
      previous_value: number | null;
      delta: number | null;
      trend_direction: string;
    };
    has_sufficient_history: boolean;
  };
  temporal_patterns: {
    morning: { slot: string; hours_label: string; count: number; mean_glucose: number | null; tir_pct: number | null; tar_pct: number | null; tbr_pct: number | null; pattern_note: string; };
    afternoon: { slot: string; hours_label: string; count: number; mean_glucose: number | null; tir_pct: number | null; tar_pct: number | null; tbr_pct: number | null; pattern_note: string; };
    evening: { slot: string; hours_label: string; count: number; mean_glucose: number | null; tir_pct: number | null; tar_pct: number | null; tbr_pct: number | null; pattern_note: string; };
    overnight: { slot: string; hours_label: string; count: number; mean_glucose: number | null; tir_pct: number | null; tar_pct: number | null; tbr_pct: number | null; pattern_note: string; };
    weekday_mean: number | null;
    weekend_mean: number | null;
    weekday_weekend_delta: number | null;
    observed_patterns: string[];
  };
  meal_associations: Array<{
    meal_timestamp: string;
    description: string;
    carbs_grams: number | null;
    glycemic_index: string | null;
    pre_meal_glucose_mg_dl: number | null;
    post_meal_peak_mg_dl: number | null;
    observed_delta_mg_dl: number | null;
    time_to_peak_minutes: number | null;
    temporal_association_note: string;
  }>;
  laboratory_profile: {
    hba1c: { latest: any | null; history: any[]; };
    creatinine: { latest: any | null; history: any[]; };
    egfr: { latest: any | null; calculated_from_creatinine: boolean; history: any[]; };
    uacr: { latest: any | null; history: any[]; };
    lipids: {
      total_cholesterol: any | null;
      ldl: any | null;
      hdl: any | null;
      triglycerides: any | null;
    };
  };
  cardiometabolic_profile: {
    blood_pressure: {
      latest_systolic: any | null;
      latest_diastolic: any | null;
      history_systolic: any[];
      history_diastolic: any[];
    };
    weight: { latest: any | null; history: any[]; };
  };
  complication_screenings: Array<{
    category: string;
    code: string;
    interval_months: number;
    last_completed_at: string | null;
    due_date: string;
    is_overdue: boolean;
    status: "CURRENT" | "DUE_SOON" | "OVERDUE" | "NO_RECORD";
  }>;
  medication_timeline: Array<{
    id: string;
    medication: string;
    dosage_instruction: string;
    status: string;
    is_active: boolean;
    start_date: string;
  }>;
  clinical_events_timeline: Array<{
    category: string;
    timestamp: string;
    title: string;
    detail: string;
    level: string;
  }>;
  ai_interpretation: {
    is_available: boolean;
    summaries: Array<{ id: string; summary: string; model_name: string | null; state: string; }>;
    disclaimer: string;
  };
  engine_metadata: {
    version: string;
    authoritative_source: string;
    generated_at: string;
    reporting_window_days: number;
  };
};

export async function fetchPatientClinicalState(
  patientId: string,
  windowDays: number = 14,
  client: ApiClient = apiClient,
  token?: string
): Promise<PatientClinicalState> {
  return client.request<PatientClinicalState>({
    method: "GET",
    path: `/api/v2/clinical/patients/${encodeURIComponent(patientId)}/clinical-state?window_days=${windowDays}`,
    token,
  });
}