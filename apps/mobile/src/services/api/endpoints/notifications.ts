import {
  notificationListResponseSchema,
  notificationResponseSchema,
  type NotificationListResponse,
  type NotificationResponse,
} from "../../schemas/notifications";
import type { EndpointDefinition } from "./types";
import { withQuery } from "./types";

export type NotificationListParams = {
  patient_id?: string;
  status?: string;
  limit?: number;
  offset?: number;
};

export function buildNotificationsPath(params?: NotificationListParams): string {
  const base = "/api/v2/notifications";
  if (!params) return base;
  const q: Record<string, string | number | undefined> = {};
  if (params.patient_id) q.patient_id = params.patient_id;
  if (params.status) q.status = params.status;
  if (params.limit !== undefined) q.limit = params.limit;
  if (params.offset !== undefined) q.offset = params.offset;
  return withQuery(base, q);
}

export const notificationsEndpoints = {
  list: {
    method: "GET",
    path: "/api/v2/notifications",
    requiresIdempotencyKey: false,
    responseSchema: notificationListResponseSchema,
  } satisfies EndpointDefinition<NotificationListResponse>,

  get: (id: string) =>
    ({
      method: "GET",
      path: `/api/v2/notifications/${encodeURIComponent(id)}`,
      requiresIdempotencyKey: false,
      responseSchema: notificationResponseSchema,
    } satisfies EndpointDefinition<NotificationResponse>),
};
