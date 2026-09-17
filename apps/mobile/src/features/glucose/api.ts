import { apiClient, type ApiClient } from "../../services/api/client";
import { clinicalEndpoints } from "../../services/api/endpoints/clinical";
import { assertPatientSafeFeed } from "./feedSafety";
import type {
  IngestGlucoseRequest,
  IngestGlucoseResponse,
  PatientObservationFeedResponse,
} from "../../services/schemas/clinical";

/**
 * Reads the patient-facing observation feed for a scoped patient.
 * The response is validated against patientObservationFeedSchema (no carbs/GI
 * allowed) and re-checked with assertPatientSafeFeed for defense-in-depth.
 */
export async function fetchObservationFeed(
  patientId: string,
  limit: number = 50,
  client: ApiClient = apiClient,
  token?: string
): Promise<PatientObservationFeedResponse> {
  const query = `?patient_id=${encodeURIComponent(patientId)}&limit=${limit}`;
  const response = await client.request<PatientObservationFeedResponse>({
    method: clinicalEndpoints.feed.method,
    path: `${clinicalEndpoints.feed.path}${query}`,
    schema: clinicalEndpoints.feed.responseSchema,
    token,
  });
  return assertPatientSafeFeed(response);
}

/**
 * Ingests a single glucose observation for a scoped patient.
 * Requires an explicit Idempotency-Key generated once per logical submission.
 */
export async function submitGlucoseReading(
  request: IngestGlucoseRequest,
  idempotencyKey: string,
  client: ApiClient = apiClient,
  token?: string
): Promise<IngestGlucoseResponse> {
  return client.request<IngestGlucoseResponse>({
    method: clinicalEndpoints.ingestGlucose.method,
    path: clinicalEndpoints.ingestGlucose.path,
    body: request,
    idempotencyKey,
    schema: clinicalEndpoints.ingestGlucose.responseSchema,
    token,
  });
}
