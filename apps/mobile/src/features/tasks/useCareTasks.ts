import { useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchCareTasks,
  fetchCareTaskDetail,
  fetchPatientDetail,
  startCareTask,
  completeCareTask,
  createCareTask,
  reassignCareTask,
} from "./api";
import { taskKeys } from "./taskKeys";
import type { CareTaskListParams } from "../../services/api/endpoints/tasks";
import {
  idempotencyKeyFor,
  InMemoryIdempotencyKeyStore,
} from "../../services/api/idempotency";
import { secureUuid } from "../../services/api/correlation";
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
import type { ApiErrorDetails } from "../../services/api/errors";

const taskKeyStore = new InMemoryIdempotencyKeyStore();

export function useCareTasks(
  params?: CareTaskListParams,
  options?: { enabled?: boolean }
) {
  return useQuery<CareTaskListResponse, ApiErrorDetails>({
    queryKey: taskKeys.list(params),
    queryFn: () => fetchCareTasks(params),
    enabled: options?.enabled ?? true,
    staleTime: 10_000,
  });
}

export function useCareTaskDetail(
  taskId: string,
  options?: { enabled?: boolean }
) {
  return useQuery<CareTaskResponse, ApiErrorDetails>({
    queryKey: taskKeys.detail(taskId),
    queryFn: () => fetchCareTaskDetail(taskId),
    enabled: Boolean(taskId) && (options?.enabled ?? true),
    staleTime: 5_000,
  });
}

export function useTaskPatient(
  patientId: string | null | undefined,
  options?: { enabled?: boolean }
) {
  return useQuery<PatientSummaryResponse, ApiErrorDetails>({
    queryKey: taskKeys.patient(patientId || ""),
    queryFn: () => fetchPatientDetail(patientId!),
    enabled: Boolean(patientId) && (options?.enabled ?? true),
    staleTime: 30_000,
  });
}

export function useStartCareTask(options?: {
  onSuccess?: (data: StartCareTaskResponse) => void;
  onError?: (error: unknown) => void;
}) {
  const queryClient = useQueryClient();
  const sessionRef = useRef<string>(secureUuid());

  return useMutation<StartCareTaskResponse, ApiErrorDetails, string>({
    mutationFn: async (taskId: string) => {
      const mutKey = `care_task:start:${taskId}:${sessionRef.current}`;
      const idempotencyKey = idempotencyKeyFor(mutKey, taskKeyStore);
      return startCareTask(taskId, undefined, undefined, idempotencyKey);
    },
    onSuccess: (data, taskId) => {
      taskKeyStore.remove(`care_task:start:${taskId}:${sessionRef.current}`);
      sessionRef.current = secureUuid(); // Reset session for next logical action
      void queryClient.invalidateQueries({ queryKey: taskKeys.lists() });
      void queryClient.invalidateQueries({ queryKey: taskKeys.detail(taskId) });
      options?.onSuccess?.(data);
    },
    onError: (error, taskId) => {
      if ((error as ApiErrorDetails)?.httpStatus === 409) {
        void queryClient.invalidateQueries({ queryKey: taskKeys.lists() });
        void queryClient.invalidateQueries({ queryKey: taskKeys.detail(taskId) });
      }
      options?.onError?.(error);
    },
  });
}

export function useCompleteCareTask(options?: {
  onSuccess?: (data: CompleteCareTaskResponse) => void;
  onError?: (error: unknown) => void;
}) {
  const queryClient = useQueryClient();
  const sessionRef = useRef<string>(secureUuid());

  return useMutation<CompleteCareTaskResponse, ApiErrorDetails, string>({
    mutationFn: async (taskId: string) => {
      const mutKey = `care_task:complete:${taskId}:${sessionRef.current}`;
      const idempotencyKey = idempotencyKeyFor(mutKey, taskKeyStore);
      return completeCareTask(taskId, undefined, undefined, idempotencyKey);
    },
    onSuccess: (data, taskId) => {
      taskKeyStore.remove(`care_task:complete:${taskId}:${sessionRef.current}`);
      sessionRef.current = secureUuid();
      void queryClient.invalidateQueries({ queryKey: taskKeys.lists() });
      void queryClient.invalidateQueries({ queryKey: taskKeys.detail(taskId) });
      options?.onSuccess?.(data);
    },
    onError: (error, taskId) => {
      if ((error as ApiErrorDetails)?.httpStatus === 409) {
        void queryClient.invalidateQueries({ queryKey: taskKeys.lists() });
        void queryClient.invalidateQueries({ queryKey: taskKeys.detail(taskId) });
      }
      options?.onError?.(error);
    },
  });
}

export function useCreateCareTask(options?: {
  onSuccess?: (data: CareTaskResponse) => void;
  onError?: (error: unknown) => void;
}) {
  const queryClient = useQueryClient();
  const sessionRef = useRef<string>(secureUuid());

  return useMutation<CareTaskResponse, ApiErrorDetails, CreateCareTaskRequest>({
    mutationFn: async (body: CreateCareTaskRequest) => {
      const mutKey = `care_task:create:${body.patient_id}:${sessionRef.current}`;
      const idempotencyKey = idempotencyKeyFor(mutKey, taskKeyStore);
      return createCareTask(body, undefined, undefined, idempotencyKey);
    },
    onSuccess: (data) => {
      sessionRef.current = secureUuid();
      void queryClient.invalidateQueries({ queryKey: taskKeys.lists() });
      options?.onSuccess?.(data);
    },
    onError: (error) => {
      options?.onError?.(error);
    },
  });
}

export function useReassignCareTask(options?: {
  onSuccess?: (data: ReassignCareTaskResponse) => void;
  onError?: (error: unknown) => void;
}) {
  const queryClient = useQueryClient();
  const sessionRef = useRef<string>(secureUuid());

  return useMutation<
    ReassignCareTaskResponse,
    ApiErrorDetails,
    { taskId: string; body: ReassignCareTaskRequest }
  >({
    mutationFn: async ({ taskId, body }) => {
      const mutKey = `care_task:reassign:${taskId}:${body.new_user_id}:${sessionRef.current}`;
      const idempotencyKey = idempotencyKeyFor(mutKey, taskKeyStore);
      return reassignCareTask(taskId, body, undefined, undefined, idempotencyKey);
    },
    onSuccess: (data, { taskId }) => {
      sessionRef.current = secureUuid();
      void queryClient.invalidateQueries({ queryKey: taskKeys.lists() });
      void queryClient.invalidateQueries({ queryKey: taskKeys.detail(taskId) });
      options?.onSuccess?.(data);
    },
    onError: (error, { taskId }) => {
      if ((error as ApiErrorDetails)?.httpStatus === 409) {
        void queryClient.invalidateQueries({ queryKey: taskKeys.lists() });
        void queryClient.invalidateQueries({ queryKey: taskKeys.detail(taskId) });
      }
      options?.onError?.(error);
    },
  });
}
