import {
  patientListResponseSchema,
  patientSummaryResponseSchema,
  patientClinicianLinkResponseSchema,
  patientClinicianLinkListResponseSchema,
  linkPatientToClinicianRequestSchema,
  type PatientListResponse,
  type PatientSummaryResponse,
  type PatientClinicianLinkResponse,
  type PatientClinicianLinkListResponse,
  type LinkPatientToClinicianRequest,
} from "../../schemas/patients";
import type { EndpointDefinition } from "./types";

export const patientsEndpoints = {
  list: {
    method: "GET",
    path: "/api/v2/patients",
    requiresIdempotencyKey: false,
    responseSchema: patientListResponseSchema,
  } satisfies EndpointDefinition<PatientListResponse, undefined>,

  detail: {
    method: "GET",
    path: (patientId: string) => `/api/v2/patients/${patientId}`,
    requiresIdempotencyKey: false,
    responseSchema: patientSummaryResponseSchema,
  } satisfies EndpointDefinition<PatientSummaryResponse, undefined>,

  documents: {
    method: "GET",
    path: (patientId: string, kind?: string) =>
      kind
        ? `/api/v2/patients/${encodeURIComponent(patientId)}/documents?kind=${encodeURIComponent(kind)}`
        : `/api/v2/patients/${encodeURIComponent(patientId)}/documents`,
    requiresIdempotencyKey: false,
  } satisfies EndpointDefinition<any, undefined>,

  clinicianLinks: {
    link: {
      method: "POST",
      path: (patientId: string) =>
        `/api/v2/patients/${encodeURIComponent(patientId)}/clinician-links`,
      requiresIdempotencyKey: true,
      requestSchema: linkPatientToClinicianRequestSchema,
      responseSchema: patientClinicianLinkResponseSchema,
    } satisfies EndpointDefinition<
      PatientClinicianLinkResponse,
      LinkPatientToClinicianRequest
    >,

    list: {
      method: "GET",
      path: (patientId: string) =>
        `/api/v2/patients/${encodeURIComponent(patientId)}/clinician-links`,
      requiresIdempotencyKey: false,
      responseSchema: patientClinicianLinkListResponseSchema,
    } satisfies EndpointDefinition<PatientClinicianLinkListResponse, undefined>,
  },
} as const;
