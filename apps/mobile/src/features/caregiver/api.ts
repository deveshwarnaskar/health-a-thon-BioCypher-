import { apiClient, type ApiClient } from "../../services/api/client";
import { caregiverEndpoints } from "../../services/api/endpoints/caregiver";
import type {
  CaregiverPatientListItem,
  CaregiverPatientListResponse,
  LinkCaregiverPatientRequest,
} from "../../services/schemas/caregiver";

/**
 * Lists the patients this caregiver is currently authorized to access
 * (Gate 10E-B). The response is validated against the strict
 * caregiverPatientListSchema — no clinical analytics or state can leak through
 * the DTO.
 */
export async function fetchCaregiverPatients(
  client: ApiClient = apiClient,
  token?: string
): Promise<CaregiverPatientListResponse> {
  return client.request<CaregiverPatientListResponse>({
    method: caregiverEndpoints.patients.method,
    path: caregiverEndpoints.patients.path,
    schema: caregiverEndpoints.patients.responseSchema,
    token,
  });
}

/**
 * Links a patient to this caregiver using the patient's UHID or ID and relationship label.
 */
export async function linkCaregiverPatient(
  request: LinkCaregiverPatientRequest,
  client: ApiClient = apiClient,
  token?: string
): Promise<CaregiverPatientListItem> {
  return client.request<CaregiverPatientListItem>({
    method: caregiverEndpoints.link.method,
    path: caregiverEndpoints.link.path,
    body: request,
    schema: caregiverEndpoints.link.responseSchema,
    token,
  });
}