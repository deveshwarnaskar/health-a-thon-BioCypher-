import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../../services/api/client";
import { medicationEndpoints } from "../../services/api/endpoints/medication";
import { patientsEndpoints } from "../../services/api/endpoints/patients";
import { notificationsEndpoints, buildNotificationsPath } from "../../services/api/endpoints/notifications";
import { fetchObservationFeed } from "../glucose/api";
import { fetchCareTasks } from "../tasks/api";
import type { MedicationPlanListResponse, MedicationPlanResponse } from "../../services/schemas/medication";
import type { NotificationListResponse, NotificationResponse } from "../../services/schemas/notifications";
import type { PatientDocument, TimelineEvent } from "./types";
import { secureUuid } from "../../services/api/correlation";

export const patientQueryKeys = {
  medications: (patientId?: string | null) => ["patient", "medications", patientId ?? "self"] as const,
  documents: (patientId?: string | null) => ["patient", "documents", patientId ?? "self"] as const,
  notifications: (patientId?: string | null) => ["patient", "notifications", patientId ?? "self"] as const,
  timeline: (patientId?: string | null) => ["patient", "timeline", patientId ?? "self"] as const,
  summary: (patientId?: string | null) => ["patient", "summary", patientId ?? "self"] as const,
};

/**
 * Reads clinician-authored medication plans for the patient.
 */
export function usePatientMedications(patientId?: string | null, options?: { enabled?: boolean }) {
  return useQuery<MedicationPlanResponse[]>({
    queryKey: patientQueryKeys.medications(patientId),
    queryFn: async () => {
      const response = await apiClient.request<MedicationPlanListResponse>({
        method: medicationEndpoints.plans.method,
        path: medicationEndpoints.plans.path,
        schema: medicationEndpoints.plans.responseSchema,
      });
      if (!patientId) return response.items;
      return response.items.filter((item) => item.patient_id === patientId);
    },
    enabled: options?.enabled ?? true,
    staleTime: 30_000,
  });
}

/**
 * Records a patient adherence event ("Mark as taken") against an active clinician-authored plan.
 */
export function useAdministerMedication(options?: {
  onSuccess?: () => void;
  onError?: (err: unknown) => void;
}) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ medicationPlanId, administeredAt }: { medicationPlanId: string; administeredAt?: string }) => {
      const idempotencyKey = secureUuid();
      return await apiClient.request({
        method: medicationEndpoints.administer.method,
        path: medicationEndpoints.administer.path,
        idempotencyKey,
        body: {
          medication_plan_id: medicationPlanId,
          administered_at: administeredAt ?? new Date().toISOString(),
        },
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["patient"] });
      options?.onSuccess?.();
    },
    onError: options?.onError,
  });
}

/**
 * Reads clinical documents and reports for the patient.
 */
export function usePatientDocuments(patientId?: string | null, options?: { enabled?: boolean }) {
  return useQuery<PatientDocument[]>({
    queryKey: patientQueryKeys.documents(patientId),
    queryFn: async () => {
      const resolved = patientId || "me";
      const response = await apiClient.request<{ total: number; items: PatientDocument[] }>({
        method: patientsEndpoints.documents.method,
        path: patientsEndpoints.documents.path(resolved),
      });
      return response.items || [];
    },
    enabled: options?.enabled ?? true,
    staleTime: 60_000,
  });
}

/**
 * Reads assistive notifications for the patient.
 */
export function usePatientNotifications(patientId?: string | null, options?: { enabled?: boolean }) {
  return useQuery<NotificationResponse[]>({
    queryKey: patientQueryKeys.notifications(patientId),
    queryFn: async () => {
      const path = buildNotificationsPath({
        patient_id: patientId ?? undefined,
        limit: 20,
      });
      const response = await apiClient.request<NotificationListResponse>({
        method: notificationsEndpoints.list.method,
        path,
        schema: notificationsEndpoints.list.responseSchema,
      });
      return response.items || [];
    },
    enabled: options?.enabled ?? true,
    staleTime: 15_000,
  });
}

/**
 * Builds a unified chronological timeline feed merging glucose, meals, and tasks.
 */
export function useUnifiedTimeline(patientId?: string | null, options?: { enabled?: boolean }) {
  return useQuery<TimelineEvent[]>({
    queryKey: patientQueryKeys.timeline(patientId),
    queryFn: async () => {
      if (!patientId) return [];

      const [observationsFeed, tasksResponse] = await Promise.all([
        fetchObservationFeed(patientId, 40).catch(() => ({ patient_id: patientId, items: [] })),
        fetchCareTasks({ patient_id: patientId, limit: 30 }).catch(() => ({ total: 0, items: [] })),
      ]);

      const events: TimelineEvent[] = [];

      // Process Observations (Glucose & Meals)
      for (const item of observationsFeed.items) {
        if (item.kind === "glucose") {
          const date = item.taken_at;
          const ctx = item.tag ? item.tag.replace("_", " ").toLowerCase() : "reading";
          events.push({
            id: `glucose-${item.taken_at}`,
            type: "glucose",
            title: `${item.value_mg_dl ?? "--"} mg/dL`,
            subtitle: `Blood Glucose · ${ctx.charAt(0).toUpperCase() + ctx.slice(1)}`,
            timestamp: date,
            status: item.confirmed ? "SYNCED" : "PENDING",
            details: { value: item.value_mg_dl, tag: item.tag },
            raw: item,
          });
        } else if (item.kind === "meal") {
          const date = item.recorded_at;
          const portion = item.portion_label || "Standard portion";
          events.push({
            id: `meal-${item.recorded_at}`,
            type: "meal",
            title: item.description,
            subtitle: `Meal logged · ${portion}`,
            timestamp: date,
            status: item.confirmed ? "SYNCED" : "PENDING",
            details: { description: item.description, portion: item.portion_label },
            raw: item,
          });
        }
      }

      // Process Tasks
      for (const t of tasksResponse.items) {
        const date = t.completed_at || t.due_at || t.created_at;
        const isDone = t.status === "completed";
        events.push({
          id: `task-${t.care_task_id}`,
          type: "task",
          title: t.description,
          subtitle: `Care task · ${isDone ? "Completed" : "Scheduled"}`,
          timestamp: date,
          status: isDone ? "SYNCED" : "PENDING",
          details: { status: t.status, due_at: t.due_at },
          raw: t,
        });
      }

      // Sort descending by timestamp
      return events.sort(
        (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
      );
    },
    enabled: Boolean(patientId) && (options?.enabled ?? true),
    staleTime: 10_000,
  });
}
