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