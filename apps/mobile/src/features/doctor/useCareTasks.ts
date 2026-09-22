import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchCareTasks, createCareTask, startCareTask, completeCareTask } from "./api";
import { doctorKeys } from "./doctorKeys";
import type { CareTaskResponse, CreateCareTaskRequest } from "../../services/schemas/tasks";

export function useCareTasks(patientId?: string, options?: { enabled?: boolean }) {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: doctorKeys.tasks(patientId),
    queryFn: () => fetchCareTasks(patientId),
    enabled: options?.enabled ?? true,
    staleTime: 30_000,
  });

  const createMutation = useMutation({
    mutationFn: (request: CreateCareTaskRequest) => {
      const idempotencyKey = `caretask-create-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
      return createCareTask(request, idempotencyKey);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: doctorKeys.tasks() });
      if (patientId) {
        queryClient.invalidateQueries({ queryKey: doctorKeys.tasks(patientId) });
      }
    },
  });

  const startMutation = useMutation({
    mutationFn: (taskId: string) => {
      const idempotencyKey = `caretask-start-${taskId}-${Date.now()}`;
      return startCareTask(taskId, idempotencyKey);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: doctorKeys.tasks() });
      if (patientId) {
        queryClient.invalidateQueries({ queryKey: doctorKeys.tasks(patientId) });
      }
    },
  });

  const completeMutation = useMutation({
    mutationFn: (taskId: string) => {
      const idempotencyKey = `caretask-complete-${taskId}-${Date.now()}`;
      return completeCareTask(taskId, idempotencyKey);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: doctorKeys.tasks() });
      if (patientId) {
        queryClient.invalidateQueries({ queryKey: doctorKeys.tasks(patientId) });
      }
    },
  });

  return {
    tasks: query.data?.items ?? [],
    taskCount: query.data?.task_count ?? 0,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
    createTask: createMutation.mutateAsync,
    isCreating: createMutation.isPending,
    startTask: startMutation.mutateAsync,
    isStarting: startMutation.isPending,
    completeTask: completeMutation.mutateAsync,
    isCompleting: completeMutation.isPending,
  };
}
