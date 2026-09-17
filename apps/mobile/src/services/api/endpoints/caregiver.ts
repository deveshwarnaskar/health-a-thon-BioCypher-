import {
  caregiverPatientListSchema,
  type CaregiverPatientListResponse,
} from "../../schemas/caregiver";
import type { EndpointDefinition } from "./types";

export const caregiverEndpoints = {
  patients: {
    method: "GET",
    path: "/api/v2/caregivers/me/patients",
    requiresIdempotencyKey: false,
    responseSchema: caregiverPatientListSchema,
  } satisfies EndpointDefinition<CaregiverPatientListResponse>,
} as const;