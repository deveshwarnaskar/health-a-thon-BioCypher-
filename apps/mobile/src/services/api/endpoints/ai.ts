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
  analyzeMealPhotoAiRequestSchema,
  analyzeMealPhotoAiResponseSchema,
  transcribeAiRequestSchema,
  transcribeAiResponseSchema,
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
  type AnalyzeMealPhotoAiRequest,
  type AnalyzeMealPhotoAiResponse,
  type TranscribeAiRequest,
  type TranscribeAiResponse,
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

  analyzeMealPhoto: {
    method: "POST",
    path: "/api/v2/ai/analyze-meal-photo",
    requiresIdempotencyKey: false,
    requestSchema: analyzeMealPhotoAiRequestSchema,
    responseSchema: analyzeMealPhotoAiResponseSchema,
  } satisfies EndpointDefinition<AnalyzeMealPhotoAiResponse, AnalyzeMealPhotoAiRequest>,

  transcribe: {
    method: "POST",
    path: "/api/v2/ai/transcribe-base64",
    requiresIdempotencyKey: false,
    requestSchema: transcribeAiRequestSchema,
    responseSchema: transcribeAiResponseSchema,
  } satisfies EndpointDefinition<TranscribeAiResponse, TranscribeAiRequest>,
} as const;