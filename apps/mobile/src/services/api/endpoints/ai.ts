import {
  aiArtifactListResponseSchema,
  aiArtifactResponseSchema,
  generateAiArtifactRequestSchema,
  generateAiArtifactResponseSchema,
  reviewAiArtifactRequestSchema,
  reviewAiArtifactResponseSchema,
  chatAiRequestSchema,
  chatAiResponseSchema,
  analyzeMealAiRequestSchema,
  analyzeMealAiResponseSchema,
  type AIArtifactListResponse,
  type AIArtifactResponse,
  type GenerateAIArtifactRequest,
  type GenerateAIArtifactResponse,
  type ReviewAIArtifactRequest,
  type ReviewAIArtifactResponse,
  type ChatAiRequest,
  type ChatAiResponse,
  type AnalyzeMealAiRequest,
  type AnalyzeMealAiResponse,
} from "../../schemas/ai";
import type { EndpointDefinition } from "./types";

export const aiEndpoints = {
  generate: {
    method: "POST",
    path: "/api/v2/clinical/ai-artifacts/generate",
    requiresIdempotencyKey: true,
    requestSchema: generateAiArtifactRequestSchema,
    responseSchema: generateAiArtifactResponseSchema,
  } satisfies EndpointDefinition<GenerateAIArtifactResponse, GenerateAIArtifactRequest>,

  queue: {
    method: "GET",
    path: "/api/v2/clinical/ai-artifacts",
    requiresIdempotencyKey: false,
    responseSchema: aiArtifactListResponseSchema,
  } satisfies EndpointDefinition<AIArtifactListResponse, undefined>,

  detail: {
    method: "GET",
    path: (artifactId: string) => `/api/v2/clinical/ai-artifacts/${artifactId}`,
    requiresIdempotencyKey: false,
    responseSchema: aiArtifactResponseSchema,
  } satisfies EndpointDefinition<AIArtifactResponse, undefined>,

  review: {
    method: "POST",
    path: (artifactId: string) => `/api/v2/clinical/ai-artifacts/${artifactId}/review`,
    requiresIdempotencyKey: true,
    requestSchema: reviewAiArtifactRequestSchema,
    responseSchema: reviewAiArtifactResponseSchema,
  } satisfies EndpointDefinition<ReviewAIArtifactResponse, ReviewAIArtifactRequest>,

  chat: {
    method: "POST",
    path: "/api/v2/ai/chat",
    requiresIdempotencyKey: false,
    requestSchema: chatAiRequestSchema,
    responseSchema: chatAiResponseSchema,
  } satisfies EndpointDefinition<ChatAiResponse, ChatAiRequest>,

  analyzeMeal: {
    method: "POST",
    path: "/api/v2/ai/analyze-meal",
    requiresIdempotencyKey: false,
    requestSchema: analyzeMealAiRequestSchema,
    responseSchema: analyzeMealAiResponseSchema,
  } satisfies EndpointDefinition<AnalyzeMealAiResponse, AnalyzeMealAiRequest>,
} as const;