import {
  reviewAiArtifactRequestSchema,
  reviewAiArtifactResponseSchema,
  type ReviewAIArtifactRequest,
  type ReviewAIArtifactResponse,
} from "../../schemas/ai";
import type { EndpointDefinition } from "./types";

export const aiEndpoints = {
  review: {
    method: "POST",
    path: (artifactId: string) => `/api/v2/clinical/ai-artifacts/${artifactId}/review`,
    requiresIdempotencyKey: true,
    requestSchema: reviewAiArtifactRequestSchema,
    responseSchema: reviewAiArtifactResponseSchema,
  } satisfies EndpointDefinition<ReviewAIArtifactResponse, ReviewAIArtifactRequest>,
} as const;