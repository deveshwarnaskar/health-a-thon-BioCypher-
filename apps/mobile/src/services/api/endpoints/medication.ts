import {
  createMedicationPlanRequestSchema,
  createMedicationPlanResponseSchema,
  type CreateMedicationPlanRequest,
  type CreateMedicationPlanResponse,
} from "../../schemas/medication";
import type { EndpointDefinition } from "./types";

export const medicationEndpoints = {
  createPlan: {
    method: "POST",
    path: "/api/v2/clinical/medication-plans",
    requiresIdempotencyKey: true,
    requestSchema: createMedicationPlanRequestSchema,
    responseSchema: createMedicationPlanResponseSchema,
  } satisfies EndpointDefinition<CreateMedicationPlanResponse, CreateMedicationPlanRequest>,
} as const;