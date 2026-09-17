import {
  careTaskListResponseSchema,
  careTaskResponseSchema,
  createCareTaskRequestSchema,
  startCareTaskResponseSchema,
  completeCareTaskResponseSchema,
  reassignCareTaskRequestSchema,
  reassignCareTaskResponseSchema,
  type CareTaskListResponse,
  type CareTaskResponse,
  type CreateCareTaskRequest,
  type StartCareTaskResponse,
  type CompleteCareTaskResponse,
  type ReassignCareTaskRequest,
  type ReassignCareTaskResponse,
} from "../../schemas/tasks";
import type { EndpointDefinition } from "./types";
import { withQuery } from "./types";

export type CareTaskListParams = {
  patient_id?: string;
  assigned_to_me?: boolean;
  assigned_to_user_id?: string;
  status?: string;
  limit?: number;
};

export function buildCareTasksPath(params?: CareTaskListParams): string {
  const base = "/api/v2/care-tasks";
  if (!params) return base;
  const q: Record<string, string | number | undefined> = {};
  if (params.patient_id) q.patient_id = params.patient_id;
  if (params.assigned_to_me) q.assigned_to_me = "true";
  if (params.assigned_to_user_id) q.assigned_to_user_id = params.assigned_to_user_id;
  if (params.status) q.status = params.status;
  if (params.limit !== undefined) q.limit = params.limit;
  return withQuery(base, q);
}

export const tasksEndpoints = {
  list: {
    method: "GET",
    path: "/api/v2/care-tasks",
    requiresIdempotencyKey: false,
    responseSchema: careTaskListResponseSchema,
  } satisfies EndpointDefinition<CareTaskListResponse, undefined>,

  detail: {
    method: "GET",
    path: (taskId: string) => `/api/v2/care-tasks/${encodeURIComponent(taskId)}`,
    requiresIdempotencyKey: false,
    responseSchema: careTaskResponseSchema,
  } satisfies EndpointDefinition<CareTaskResponse, undefined>,

  create: {
    method: "POST",
    path: "/api/v2/care-tasks",
    requiresIdempotencyKey: true,
    requestSchema: createCareTaskRequestSchema,
    responseSchema: careTaskResponseSchema,
  } satisfies EndpointDefinition<CareTaskResponse, CreateCareTaskRequest>,

  start: {
    method: "POST",
    path: (taskId: string) => `/api/v2/care-tasks/${encodeURIComponent(taskId)}/start`,
    requiresIdempotencyKey: true,
    responseSchema: startCareTaskResponseSchema,
  } satisfies EndpointDefinition<StartCareTaskResponse, undefined>,

  complete: {
    method: "POST",
    path: (taskId: string) => `/api/v2/care-tasks/${encodeURIComponent(taskId)}/complete`,
    requiresIdempotencyKey: true,
    responseSchema: completeCareTaskResponseSchema,
  } satisfies EndpointDefinition<CompleteCareTaskResponse, undefined>,

  reassign: {
    method: "POST",
    path: (taskId: string) => `/api/v2/care-tasks/${encodeURIComponent(taskId)}/reassign`,
    requiresIdempotencyKey: true,
    requestSchema: reassignCareTaskRequestSchema,
    responseSchema: reassignCareTaskResponseSchema,
  } satisfies EndpointDefinition<ReassignCareTaskResponse, ReassignCareTaskRequest>,
} as const;
