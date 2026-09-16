import { authVerifyResponseSchema, type AuthVerifyResponse } from "../../schemas/auth";
import type { EndpointDefinition } from "./types";

export const authEndpoints = {
  verify: {
    method: "GET",
    path: "/api/v2/auth/verify",
    requiresIdempotencyKey: false,
    responseSchema: authVerifyResponseSchema,
  } satisfies EndpointDefinition<AuthVerifyResponse>,
} as const;