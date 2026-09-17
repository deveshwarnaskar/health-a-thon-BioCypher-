import { apiClient, type ApiClient } from "../../services/api/client";
import {
  tasksEndpoints,
  buildCareTasksPath,
  type CareTaskListParams,
} from "../../services/api/endpoints/tasks";
import { patientsEndpoints } from "../../services/api/endpoints/patients";
import type {
  CareTaskListResponse,
  CareTaskResponse,
  CreateCareTaskRequest,
  StartCareTaskResponse,
  CompleteCareTaskResponse,
  ReassignCareTaskRequest,
  ReassignCareTaskResponse,
} from "../../services/schemas/tasks";
import type { PatientSummaryResponse } from "../../services/schemas/patients";

export async function fetchCareTasks(
  params?: CareTaskListParams,
  client: ApiClient = apiClient,
  token?: string
): Promise<CareTaskListResponse> {
  return client.request<CareTaskListResponse>({
    method: tasksEndpoints.list.method,
    path: buildCareTasksPath(params),
    schema: tasksEndpoints.list.responseSchema,
    token,
  });
}

export async function fetchCareTaskDetail(
  taskId: string,
  client: ApiClient = apiClient,
  token?: string
): Promise<CareTaskResponse> {
  return client.request<CareTaskResponse>({
    method: tasksEndpoints.detail.method,
    path: tasksEndpoints.detail.path(taskId),
    schema: tasksEndpoints.detail.responseSchema,
    token,
  });
}

export async function createCareTask(
  body: CreateCareTaskRequest,
  client: ApiClient = apiClient,
  token?: string,
  idempotencyKey?: string
): Promise<CareTaskResponse> {
  return client.request<CareTaskResponse>({
    method: tasksEndpoints.create.method,
    path: tasksEndpoints.create.path,
    body,
    schema: tasksEndpoints.create.responseSchema,
    token,
    idempotencyKey,
  });
}

export async function startCareTask(
  taskId: string,
  client: ApiClient = apiClient,
  token?: string,
  idempotencyKey?: string
): Promise<StartCareTaskResponse> {
  return client.request<StartCareTaskResponse>({
    method: tasksEndpoints.start.method,
    path: tasksEndpoints.start.path(taskId),
    body: {},
    schema: tasksEndpoints.start.responseSchema,
    token,
    idempotencyKey,
  });
}

export async function completeCareTask(
  taskId: string,
  client: ApiClient = apiClient,
  token?: string,
  idempotencyKey?: string
): Promise<CompleteCareTaskResponse> {
  return client.request<CompleteCareTaskResponse>({
    method: tasksEndpoints.complete.method,
    path: tasksEndpoints.complete.path(taskId),
    body: {},
    schema: tasksEndpoints.complete.responseSchema,
    token,
    idempotencyKey,
  });
}

export async function reassignCareTask(
  taskId: string,
  body: ReassignCareTaskRequest,
  client: ApiClient = apiClient,
  token?: string,
  idempotencyKey?: string
): Promise<ReassignCareTaskResponse> {
  return client.request<ReassignCareTaskResponse>({
    method: tasksEndpoints.reassign.method,
    path: tasksEndpoints.reassign.path(taskId),
    body,
    schema: tasksEndpoints.reassign.responseSchema,
    token,
    idempotencyKey,
  });
}

export async function fetchPatientDetail(
  patientId: string,
  client: ApiClient = apiClient,
  token?: string
): Promise<PatientSummaryResponse> {
  return client.request<PatientSummaryResponse>({
    method: patientsEndpoints.detail.method,
    path: patientsEndpoints.detail.path(patientId),
    schema: patientsEndpoints.detail.responseSchema,
    token,
  });
}
