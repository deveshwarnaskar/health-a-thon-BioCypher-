import { z } from "zod";

// ─── Care Task Schemas (Gate 10J-B Backend Contracts → Gate 10J-M) ──────────

export const careTaskStatusSchema = z.enum(["open", "in_progress", "completed", "cancelled"]);
export type CareTaskStatus = z.infer<typeof careTaskStatusSchema>;

export const careTaskResponseSchema = z
  .object({
    care_task_id: z.string(),
    patient_id: z.string(),
    assigned_to_user_id: z.string(),
    description: z.string(),
    status: careTaskStatusSchema,
    due_at: z.string().nullable().optional(),
    created_at: z.string(),
    completed_at: z.string().nullable().optional(),
  })
  .strict();
export type CareTaskResponse = z.infer<typeof careTaskResponseSchema>;

export const careTaskListResponseSchema = z
  .object({
    patient_id: z.string().nullable().optional(),
    task_count: z.number().int(),
    items: z.array(careTaskResponseSchema),
  })
  .strict();
export type CareTaskListResponse = z.infer<typeof careTaskListResponseSchema>;

export const createCareTaskRequestSchema = z
  .object({
    patient_id: z.string(),
    assigned_to_user_id: z.string(),
    description: z.string().min(1),
    due_at: z.string().optional(),
  })
  .strict();
export type CreateCareTaskRequest = z.infer<typeof createCareTaskRequestSchema>;

export const startCareTaskResponseSchema = z
  .object({
    care_task_id: z.string(),
    status: z.literal("in_progress"),
  })
  .strict();
export type StartCareTaskResponse = z.infer<typeof startCareTaskResponseSchema>;

export const completeCareTaskResponseSchema = z
  .object({
    care_task_id: z.string(),
    status: z.literal("completed"),
    completed_at: z.string(),
  })
  .strict();
export type CompleteCareTaskResponse = z.infer<typeof completeCareTaskResponseSchema>;

export const reassignCareTaskRequestSchema = z
  .object({
    new_user_id: z.string(),
  })
  .strict();
export type ReassignCareTaskRequest = z.infer<typeof reassignCareTaskRequestSchema>;

export const reassignCareTaskResponseSchema = z
  .object({
    care_task_id: z.string(),
    assigned_to_user_id: z.string(),
    status: careTaskStatusSchema,
  })
  .strict();
export type ReassignCareTaskResponse = z.infer<typeof reassignCareTaskResponseSchema>;
