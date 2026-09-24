import {
  caregiverPatientListSchema,
  caregiverPatientListItemSchema,
  linkCaregiverPatientRequestSchema,
  type CaregiverPatientListResponse,
  type CaregiverPatientListItem,
  type LinkCaregiverPatientRequest,
} from "../../schemas/caregiver";
import type { EndpointDefinition } from "./types";

export const caregiverEndpoints = {
  patients: {
    method: "GET",
    path: "/api/v2/caregivers/me/patients",
    requiresIdempotencyKey: false,
    responseSchema: caregiverPatientListSchema,
  } satisfies EndpointDefinition<CaregiverPatientListResponse>,

  link: {
    method: "POST",
    path: "/api/v2/caregivers/link",
    requiresIdempotencyKey: false,
    requestSchema: linkCaregiverPatientRequestSchema,
    responseSchema: caregiverPatientListItemSchema,
  } satisfies EndpointDefinition<CaregiverPatientListItem, LinkCaregiverPatientRequest>,
} as const;