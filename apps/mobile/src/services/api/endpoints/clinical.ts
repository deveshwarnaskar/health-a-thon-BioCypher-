import {
  ingestGlucoseRequestSchema,
  ingestGlucoseResponseSchema,
  patientObservationFeedSchema,
  type IngestGlucoseRequest,
  type IngestGlucoseResponse,
  type PatientObservationFeedResponse,
} from "../../schemas/clinical";
import type { EndpointDefinition } from "./types";

export type ObservationFeedQuery = {
  patient_id: string;
  limit?: number;
};

export const clinicalEndpoints = {
  feed: {
    method: "GET",
    path: "/api/v2/clinical/observations",
    requiresIdempotencyKey: false,
    responseSchema: patientObservationFeedSchema,
  } satisfies EndpointDefinition<PatientObservationFeedResponse, undefined>,

  ingestGlucose: {
    method: "POST",
    path: "/api/v2/clinical/observations",
    requiresIdempotencyKey: true,
    requestSchema: ingestGlucoseRequestSchema,
    responseSchema: ingestGlucoseResponseSchema,
  } satisfies EndpointDefinition<IngestGlucoseResponse, IngestGlucoseRequest>,
} as const;