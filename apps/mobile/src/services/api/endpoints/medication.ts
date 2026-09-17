import {
  createMedicationPlanRequestSchema,
  createMedicationPlanResponseSchema,
  medicationPlanListResponseSchema,
  medicationPlanResponseSchema,
  type CreateMedicationPlanRequest,
  type CreateMedicationPlanResponse,
  type MedicationPlanListResponse,
  type MedicationPlanResponse,
} from "../../schemas/medication";
import type { EndpointDefinition } from "./types";

export const medicationEndpoints = {
  plans: {
    method: "GET",
    path: "/api/v2/clinical/medication-plans",
    requiresIdempotencyKey: false,
    responseSchema: medicationPlanListResponseSchema,
  } satisfies EndpointDefinition<MedicationPlanListResponse, undefined>,

  planDetail: {
    method: "GET",
    path: (planId: string) => `/api/v2/clinical/medication-plans/${planId}`,
    requiresIdempotencyKey: false,
    responseSchema: medicationPlanResponseSchema,
  } satisfies EndpointDefinition<MedicationPlanResponse, undefined>,

  createPlan: {
    method: "POST",
    path: "/api/v2/clinical/medication-plans",
    requiresIdempotencyKey: true,
    requestSchema: createMedicationPlanRequestSchema,
    responseSchema: createMedicationPlanResponseSchema,
  } satisfies EndpointDefinition<CreateMedicationPlanResponse, CreateMedicationPlanRequest>,
} as const;