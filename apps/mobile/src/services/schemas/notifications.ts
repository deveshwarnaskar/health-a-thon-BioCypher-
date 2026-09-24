import { z } from "zod";

// ─── Notification Schemas (Gate 10L Backend Contracts) ──────────────────────

export const notificationStatusSchema = z.enum([
  "pending",
  "queued",
  "delivering",
  "delivered",
  "failed",
  "cancelled",
]);
export type NotificationStatus = z.infer<typeof notificationStatusSchema>;

export const notificationChannelSchema = z.enum(["WHATSAPP", "SMS", "IN_APP"]);
export type NotificationChannel = z.infer<typeof notificationChannelSchema>;

export const notificationTypeSchema = z.enum([
  "reminder",
  "alert",
  "task_assigned",
  "care_update",
  "clinical_communication",
]);
export type NotificationType = z.infer<typeof notificationTypeSchema>;

export const notificationResponseSchema = z
  .object({
    id: z.string(),
    tenant_id: z.string(),
    recipient_id: z.string(),
    recipient_phone: z.string(),
    patient_id: z.string().nullable().optional(),
    notification_type: z.string(),
    channel: z.string(),
    template_name: z.string(),
    template_params: z.record(z.string(), z.string()),
    status: notificationStatusSchema,
    created_at: z.string(),
    scheduled_at: z.string().nullable().optional(),
    delivered_at: z.string().nullable().optional(),
    failed_at: z.string().nullable().optional(),
    failure_reason: z.string().nullable().optional(),
    correlation_id: z.string().nullable().optional(),
    retry_count: z.number().int(),
  })
  .strict();
export type NotificationResponse = z.infer<typeof notificationResponseSchema>;

export const notificationListResponseSchema = z
  .object({
    total: z.number().int(),
    items: z.array(notificationResponseSchema),
  })
  .strict();
export type NotificationListResponse = z.infer<typeof notificationListResponseSchema>;
