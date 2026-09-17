import type { CareTaskListParams } from "../../services/api/endpoints/tasks";

/**
 * Care-task query-family keys (Gate 10J-M).
 * Server state only; never persisted locally.
 */
export const taskKeys = {
  all: ["care-tasks"] as const,
  lists: () => ["care-tasks", "list"] as const,
  list: (params?: CareTaskListParams) => ["care-tasks", "list", params ?? {}] as const,
  detail: (taskId: string) => ["care-tasks", "detail", taskId] as const,
  patient: (patientId: string) => ["care-tasks", "patient", patientId] as const,
} as const;
