import {
  patientListResponseSchema,
  patientSummaryResponseSchema,
  type PatientListResponse,
  type PatientSummaryResponse,
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
} as const;