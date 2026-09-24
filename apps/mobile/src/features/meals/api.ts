import { apiClient, type ApiClient } from "../../services/api/client";
import { clinicalEndpoints } from "../../services/api/endpoints/clinical";
import { mealsEndpoints } from "../../services/api/endpoints/meals";
import { assertPatientSafeFeed } from "../glucose/feedSafety";
import type {
  ConfirmMealRequest,
  ConfirmMealResponse,
  LogMealRequest,
  LogMealResponse,
} from "../../services/schemas/meals";
import type {
  ClinicianMealObservation,
  ClinicianObservationFeedResponse,
  PatientMealObservation,
  PatientObservationFeedResponse,
} from "../../services/schemas/clinical";

/**
 * Drafts a new meal observation (POST /api/v2/clinical/meals).
 * Requires Gate 09 Idempotency-Key.
 */
export async function submitMealDraft(
  request: LogMealRequest,
  idempotencyKey: string,
  client: ApiClient = apiClient,
  token?: string
): Promise<LogMealResponse> {
  return client.request<LogMealResponse>({
    method: mealsEndpoints.logDraft.method,
    path: mealsEndpoints.logDraft.path as string,
    body: request,
    idempotencyKey,
    schema: mealsEndpoints.logDraft.responseSchema,
    token,
  });
}

/**
 * Confirms or corrects a pending meal observation (POST /api/v2/clinical/meals/{id}/confirm).
 * Patient confirmation authority only (Domain Gate 03).
 */
export async function submitMealConfirmation(
  mealObservationId: string,
  request: ConfirmMealRequest,
  idempotencyKey: string,
  client: ApiClient = apiClient,
  token?: string
): Promise<ConfirmMealResponse> {
  return client.request<ConfirmMealResponse>({
    method: mealsEndpoints.confirm.method,
    path: mealsEndpoints.confirm.path(mealObservationId),
    body: request,
    idempotencyKey,
    schema: mealsEndpoints.confirm.responseSchema,
    token,
  });
}

/**
 * Fetches the patient observation feed and returns only meal observations.
 * Defense-in-depth: runs assertPatientSafeFeed to ensure carbs_grams and
 * glycemic_index are NEVER leaked to the patient.
 */
export async function fetchPatientMeals(
  patientId: string,
  limit: number = 50,
  client: ApiClient = apiClient,
  token?: string
): Promise<PatientMealObservation[]> {
  const query = `?patient_id=${encodeURIComponent(patientId)}&limit=${limit}`;
  const response = await client.request<PatientObservationFeedResponse>({
    method: clinicalEndpoints.feed.method,
    path: `${clinicalEndpoints.feed.path}${query}`,
    schema: clinicalEndpoints.feed.responseSchema,
    token,
  });
  const safeResponse = assertPatientSafeFeed(response);
  return safeResponse.items.filter(
    (item): item is PatientMealObservation => item.kind === "meal"
  );
}

/**
 * Fetches the clinician observation feed and returns clinician meal observations
 * with analytical metadata (carbs_grams, glycemic_index, confirmation status).
 */
export async function fetchClinicianMeals(
  patientId: string,
  client: ApiClient = apiClient,
  token?: string
): Promise<ClinicianMealObservation[]> {
  const query = `?patient_id=${encodeURIComponent(patientId)}`;
  const response = await client.request<ClinicianObservationFeedResponse>({
    method: clinicalEndpoints.clinicianFeed.method,
    path: `${clinicalEndpoints.clinicianFeed.path}${query}`,
    schema: clinicalEndpoints.clinicianFeed.responseSchema,
    token,
  });
  return response.items.filter(
    (item): item is ClinicianMealObservation => item.kind === "meal"
  );
}
