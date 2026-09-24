import {
  confirmMealRequestSchema,
  confirmMealResponseSchema,
  logMealRequestSchema,
  logMealResponseSchema,
  type ConfirmMealRequest,
  type ConfirmMealResponse,
  type LogMealRequest,
  type LogMealResponse,
} from "../../schemas/meals";
import type { EndpointDefinition } from "./types";

export const mealsEndpoints = {
  logDraft: {
    method: "POST",
    path: "/api/v2/clinical/meals",
    requiresIdempotencyKey: true,
    requestSchema: logMealRequestSchema,
    responseSchema: logMealResponseSchema,
  } satisfies EndpointDefinition<LogMealResponse, LogMealRequest>,

  confirm: {
    method: "POST",
    path: (mealObservationId: string) => `/api/v2/clinical/meals/${encodeURIComponent(mealObservationId)}/confirm`,
    requiresIdempotencyKey: true,
    requestSchema: confirmMealRequestSchema,
    responseSchema: confirmMealResponseSchema,
  } satisfies EndpointDefinition<ConfirmMealResponse, ConfirmMealRequest>,
} as const;
