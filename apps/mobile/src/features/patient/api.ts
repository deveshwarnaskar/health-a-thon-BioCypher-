import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../../services/api/client";
import { medicationEndpoints } from "../../services/api/endpoints/medication";
import { patientsEndpoints } from "../../services/api/endpoints/patients";
import { notificationsEndpoints, buildNotificationsPath } from "../../services/api/endpoints/notifications";
import { aiEndpoints } from "../../services/api/endpoints/ai";
import { fetchObservationFeed } from "../glucose/api";
import { fetchCareTasks } from "../tasks/api";
import type { MedicationPlanListResponse, MedicationPlanResponse } from "../../services/schemas/medication";
import type { NotificationListResponse, NotificationResponse } from "../../services/schemas/notifications";
import type { ChatAiResponse, AnalyzeMealAiResponse } from "../../services/schemas/ai";
import type { PatientDocument, TimelineEvent } from "./types";
import { secureUuid } from "../../services/api/correlation";
import { connectivityService } from "../../connectivity/connectivityService";
import { localDatabase } from "../../db/database";
import { localSessionIsolation } from "../../db/isolation";
import { OfflineCaptureService } from "../../sync/offlineCapture";
import { GlucoseRepository, MealRepository } from "../../db/repositories";
import { getSecondaryEvents, saveSecondaryEvent } from "./secondaryStorage";

export const patientQueryKeys = {
  medications: (patientId?: string | null) => ["patient", "medications", patientId ?? "self"] as const,
  documents: (patientId?: string | null) => ["patient", "documents", patientId ?? "self"] as const,
  notifications: (patientId?: string | null) => ["patient", "notifications", patientId ?? "self"] as const,
  timeline: (patientId?: string | null) => ["patient", "timeline", patientId ?? "self"] as const,
  summary: (patientId?: string | null) => ["patient", "summary", patientId ?? "self"] as const,
};

/**
 * Reads clinician-authored medication plans for the patient.
 * The patient cannot modify plans, prescribe, or titrate (Section 4.1.B & 11).
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
 * Records a patient adherence event ("Mark as taken" / Two-stage response)
 * against an active clinician-authored plan with transparent offline support (Section 4.1.C & 12).
 */
export function useAdministerMedication(options?: {
  onSuccess?: () => void;
  onError?: (err: unknown) => void;
}) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      medicationPlanId,
      administeredAt,
    }: {
      medicationPlanId: string;
      administeredAt?: string;
    }) => {
      const idempotencyKey = secureUuid();
      const actualTime = administeredAt ?? new Date().toISOString();

      // Offline capture path when disconnected
      if (
        !connectivityService.isOnline() &&
        localDatabase.isOpen() &&
        localSessionIsolation.hasContext()
      ) {
        const offlineService = new OfflineCaptureService(localDatabase.getDb());
        const context = localSessionIsolation.getContext();
        return await offlineService.captureMedicationAdministration(
          context,
          medicationPlanId,
          actualTime,
          idempotencyKey
        );
      }

      try {
        return await apiClient.request({
          method: medicationEndpoints.administer.method,
          path: medicationEndpoints.administer.path,
          idempotencyKey,
          body: {
            medication_plan_id: medicationPlanId,
            administered_at: actualTime,
          },
        });
      } catch (err: any) {
        // Fallback to local outbox on network drop
        if (
          (err?.kind === "NETWORK_ERROR" || !err?.httpStatus) &&
          localDatabase.isOpen() &&
          localSessionIsolation.hasContext()
        ) {
          const offlineService = new OfflineCaptureService(localDatabase.getDb());
          const context = localSessionIsolation.getContext();
          return await offlineService.captureMedicationAdministration(
            context,
            medicationPlanId,
            actualTime,
            idempotencyKey
          );
        }
        throw err;
      }
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
 * Uploads a document or lab report with offline outbox queuing fallback (Section 8 & 30).
 */
export function useUploadPatientDocument(
  patientId?: string | null,
  options?: {
    onSuccess?: () => void;
    onError?: (err: unknown) => void;
  }
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      filename,
      mimeType,
      contentBase64,
      kind,
    }: {
      filename: string;
      mimeType: string;
      contentBase64: string;
      kind?: string;
    }) => {
      const resolved = patientId || "me";
      const idempotencyKey = secureUuid();

      if (
        !connectivityService.isOnline() &&
        localDatabase.isOpen() &&
        localSessionIsolation.hasContext()
      ) {
        const offlineService = new OfflineCaptureService(localDatabase.getDb());
        const context = localSessionIsolation.getContext();
        return await offlineService.captureDocumentUpload(
          context,
          resolved,
          {
            filename,
            mime_type: mimeType,
            content_base64: contentBase64,
            kind,
          },
          idempotencyKey
        );
      }

      try {
        return await apiClient.request({
          method: "POST",
          path: `/api/v2/clinical/patients/${encodeURIComponent(resolved)}/documents/upload`,
          idempotencyKey,
          body: {
            filename,
            mime_type: mimeType,
            content_base64: contentBase64,
            kind: kind ?? "chart_image",
          },
        });
      } catch (err: any) {
        if (
          (err?.kind === "NETWORK_ERROR" || !err?.httpStatus) &&
          localDatabase.isOpen() &&
          localSessionIsolation.hasContext()
        ) {
          const offlineService = new OfflineCaptureService(localDatabase.getDb());
          const context = localSessionIsolation.getContext();
          return await offlineService.captureDocumentUpload(
            context,
            resolved,
            {
              filename,
              mime_type: mimeType,
              content_base64: contentBase64,
              kind,
            },
            idempotencyKey
          );
        }
        throw err;
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: patientQueryKeys.documents(patientId) });
      queryClient.invalidateQueries({ queryKey: patientQueryKeys.timeline(patientId) });
      options?.onSuccess?.();
    },
    onError: options?.onError,
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
 * Builds a unified chronological timeline feed merging glucose, meals, medication, tasks,
 * and locally persisted offline events (Section 9, 30, 47).
 */
export function useUnifiedTimeline(patientId?: string | null, options?: { enabled?: boolean }) {
  return useQuery<TimelineEvent[]>({
    queryKey: patientQueryKeys.timeline(patientId),
    queryFn: async () => {
      if (!patientId) return [];

      const [observationsFeed, tasksResponse, documentsResponse, plansResponse] = await Promise.all([
        fetchObservationFeed(patientId, 40).catch(() => ({ patient_id: patientId, items: [] })),
        fetchCareTasks({ patient_id: patientId, limit: 30 }).catch(() => ({ total: 0, items: [] })),
        apiClient
          .request<{ total: number; items: PatientDocument[] }>({
            method: patientsEndpoints.documents.method,
            path: patientsEndpoints.documents.path(patientId),
          })
          .catch(() => ({ total: 0, items: [] })),
        apiClient
          .request<MedicationPlanListResponse>({
            method: medicationEndpoints.plans.method,
            path: medicationEndpoints.plans.path,
            schema: medicationEndpoints.plans.responseSchema,
          })
          .catch(() => ({ total: 0, items: [] })),
      ]);

      const events: TimelineEvent[] = [];
      const seenGlucoseKeys = new Set<string>();
      const seenMealKeys = new Set<string>();

      // 1. Process Remote Observations (Glucose & Meals)
      for (const item of observationsFeed.items) {
        if (item.kind === "glucose") {
          seenGlucoseKeys.add(item.taken_at);
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
          seenMealKeys.add(item.recorded_at);
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

      // 2. Query Local Encrypted SQLite for offline or unsynced records (Gate 10O / Section 30)
      if (localDatabase.isOpen() && localSessionIsolation.hasContext()) {
        try {
          const ctx = localSessionIsolation.getContext();
          const glucoseRepo = new GlucoseRepository(localDatabase.getDb());
          const mealRepo = new MealRepository(localDatabase.getDb());

          const [localGlucose, localMeals] = await Promise.all([
            glucoseRepo.findByPatient(ctx, patientId).catch(() => []),
            mealRepo.findByPatient(ctx, patientId).catch(() => []),
          ]);

          for (const lg of localGlucose) {
            if (!seenGlucoseKeys.has(lg.takenAt)) {
              seenGlucoseKeys.add(lg.takenAt);
              const tagStr = lg.tag ? lg.tag.replace("_", " ").toLowerCase() : "reading";
              events.push({
                id: `local-glucose-${lg.localId}`,
                type: "glucose",
                title: `${lg.valueMgDl} mg/dL`,
                subtitle: `Blood Glucose · ${tagStr.charAt(0).toUpperCase() + tagStr.slice(1)}`,
                timestamp: lg.takenAt,
                status: lg.syncStatus === "SYNCED" ? "SYNCED" : "SAVED_LOCALLY",
                details: { value: lg.valueMgDl, tag: lg.tag },
              });
            }
          }

          for (const lm of localMeals) {
            if (!seenMealKeys.has(lm.recordedAt)) {
              seenMealKeys.add(lm.recordedAt);
              events.push({
                id: `local-meal-${lm.localId}`,
                type: "meal",
                title: lm.description,
                subtitle: `Meal logged · ${lm.portionSize || "Standard portion"}`,
                timestamp: lm.recordedAt,
                status: lm.syncStatus === "SYNCED" ? "SYNCED" : "SAVED_LOCALLY",
                details: { description: lm.description, portion: lm.portionSize },
              });
            }
          }

          // 2c. Query local offline documents (Gate 10N / Section 12)
          const localDocs: any[] = await localDatabase.getDb().getAllAsync(
            "SELECT id, filename, kind, file_size_bytes, created_at FROM local_documents WHERE tenant_id = ? AND user_id = ?",
            [ctx.tenantId, ctx.userId]
          ).catch(() => []);

          const seenDocNames = new Set((documentsResponse.items || []).map((d: PatientDocument) => d.filename));

          for (const ld of localDocs) {
            if (!seenDocNames.has(ld.filename)) {
              seenDocNames.add(ld.filename);
              const kindLabel =
                ld.kind === "lab_report"
                  ? "Lab Report"
                  : ld.kind === "prescription"
                    ? "Prescription"
                    : "Clinical Document";
              events.push({
                id: `local-doc-${ld.id}`,
                type: "document",
                title: ld.filename,
                subtitle: `${kindLabel} · Saved locally`,
                timestamp: ld.created_at,
                status: "SAVED_LOCALLY",
                details: { filename: ld.filename, kind: ld.kind, size: ld.file_size_bytes },
              });
            }
          }

          // 2d. Query local offline medication administrations from outbox (Gate 10O / Section 12)
          const pendingMeds: any[] = await localDatabase.getDb().getAllAsync(
            "SELECT id, payload_json, created_at FROM mutation_outbox WHERE tenant_id = ? AND user_id = ? AND mutation_type = 'ADMINISTER_MEDICATION' AND sync_status != 'SYNCED'",
            [ctx.tenantId, ctx.userId]
          ).catch(() => []);

          for (const pm of pendingMeds) {
            try {
              const payload = JSON.parse(pm.payload_json);
              events.push({
                id: `local-med-admin-${pm.id}`,
                type: "medication",
                title: "Medication Dose Administered",
                subtitle: "Recorded offline · Pending server sync",
                timestamp: payload.administered_at || pm.created_at,
                status: "SAVED_LOCALLY",
                details: { medication_plan_id: payload.medication_plan_id, administered_at: payload.administered_at },
              });
            } catch {}
          }
        } catch {}
      }

      // 3. Process Tasks
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

      // 4. Process Prescribed Medication Plans (Clinician-authored)
      const patientPlans = (plansResponse.items || []).filter(
        (p) => !p.patient_id || p.patient_id === patientId
      );
      for (const plan of patientPlans) {
        events.push({
          id: `medplan-${plan.medication_plan_id}`,
          type: "medication",
          title: plan.medication,
          subtitle: `Prescription · ${plan.instruction || "Take as prescribed"}`,
          timestamp: plan.created_at,
          status: "SYNCED",
          details: { medication: plan.medication, instruction: plan.instruction },
          raw: plan,
        });
      }

      // 5. Process Clinical Documents
      for (const doc of documentsResponse.items || []) {
        events.push({
          id: `doc-${doc.id}`,
          type: "document",
          title: doc.filename,
          subtitle: `Document · ${doc.kind || "Clinical Report"}`,
          timestamp: doc.created_at,
          status: "SYNCED",
          details: { kind: doc.kind, filename: doc.filename },
        });
      }

      // 6. Process Secondary Events (Activity, Vitals, Symptoms, Sleep)
      const secondaryEvents = await getSecondaryEvents(patientId);
      for (const sec of secondaryEvents) {
        events.push(sec);
      }

      // Sort descending by timestamp / occurred_at
      return events.sort(
        (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
      );
    },
    enabled: Boolean(patientId) && (options?.enabled ?? true),
    staleTime: 10_000,
  });
}

/**
 * Communicates with the live Sarvam AI Health Assistant (POST /api/v2/ai/chat).
 * Empathetic Indic health dialogue with emergency triage & ICMR boundary guards.
 */
export function useSarvamChat() {
  return useMutation<ChatAiResponse, Error, { message: string; patientName?: string }>({
    mutationFn: async ({ message, patientName }) => {
      return apiClient.request<ChatAiResponse>({
        method: aiEndpoints.chat.method,
        path: aiEndpoints.chat.path,
        body: { message, patient_name: patientName },
        schema: aiEndpoints.chat.responseSchema,
      });
    },
  });
}

/**
 * Analyzes Indian meals using ICMR-NIN tables and Sarvam LLM (POST /api/v2/ai/analyze-meal).
 */
export function useSarvamMealAnalysis() {
  return useMutation<AnalyzeMealAiResponse, Error, { description: string; patientName?: string }>({
    mutationFn: async ({ description, patientName }) => {
      return apiClient.request<AnalyzeMealAiResponse>({
        method: aiEndpoints.analyzeMeal.method,
        path: aiEndpoints.analyzeMeal.path,
        body: { description, patient_name: patientName },
        schema: aiEndpoints.analyzeMeal.responseSchema,
      });
    },
  });
}

/**
 * Saves a physical activity event to local durable persistence and refreshes timeline.
 */
export function useSaveActivity(options?: { onSuccess?: () => void }) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      patientId,
      type,
      durationMinutes,
      intensity,
      date,
      time,
      notes,
    }: {
      patientId: string;
      type: string;
      durationMinutes: number;
      intensity: string;
      date: string;
      time: string;
      notes?: string;
    }) => {
      const typeCapitalized = type.charAt(0).toUpperCase() + type.slice(1);
      const intensityCapitalized = intensity.charAt(0).toUpperCase() + intensity.slice(1);
      return await saveSecondaryEvent({
        patientId,
        type: "activity",
        title: `${typeCapitalized} · ${durationMinutes} min`,
        subtitle: `${intensityCapitalized} intensity · ${time}`,
        timestamp: `${date}T${time}:00Z`,
        details: { type, durationMinutes, intensity, notes },
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["patient"] });
      options?.onSuccess?.();
    },
  });
}

/**
 * Saves a body weight event to local durable persistence and refreshes timeline.
 */
export function useSaveWeight(options?: { onSuccess?: () => void }) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      patientId,
      weight,
      unit,
      context,
      date,
      time,
      notes,
    }: {
      patientId: string;
      weight: number;
      unit: string;
      context?: string;
      date: string;
      time: string;
      notes?: string;
    }) => {
      return await saveSecondaryEvent({
        patientId,
        type: "vital",
        title: `${weight} ${unit}`,
        subtitle: `Body Weight · ${context || "Measurement"}`,
        timestamp: `${date}T${time}:00Z`,
        details: { weight, unit, context, notes },
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["patient"] });
      options?.onSuccess?.();
    },
  });
}

/**
 * Saves a blood pressure event to local durable persistence and refreshes timeline.
 */
export function useSaveBloodPressure(options?: { onSuccess?: () => void }) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      patientId,
      systolic,
      diastolic,
      pulse,
      position,
      date,
      time,
      notes,
    }: {
      patientId: string;
      systolic: number;
      diastolic: number;
      pulse?: number;
      position?: string;
      date: string;
      time: string;
      notes?: string;
    }) => {
      const pulseStr = pulse ? ` · ${pulse} bpm` : "";
      const posStr = position ? ` (${position})` : "";
      return await saveSecondaryEvent({
        patientId,
        type: "vital",
        title: `${systolic}/${diastolic} mmHg`,
        subtitle: `Blood Pressure${pulseStr}${posStr}`,
        timestamp: `${date}T${time}:00Z`,
        details: { systolic, diastolic, pulse, position, notes },
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["patient"] });
      options?.onSuccess?.();
    },
  });
}

/**
 * Saves a patient-reported symptom or event to local durable persistence.
 */
export function useSaveSymptoms(options?: { onSuccess?: () => void }) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      patientId,
      selectedSymptoms,
      nearbyGlucose,
      date,
      time,
      notes,
    }: {
      patientId: string;
      selectedSymptoms: string[];
      nearbyGlucose?: number;
      date: string;
      time: string;
      notes?: string;
    }) => {
      const formatted = selectedSymptoms
        .map((s) => s.replace("_", " "))
        .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
        .join(", ");
      const gStr = nearbyGlucose ? ` · Reading: ${nearbyGlucose} mg/dL` : "";
      return await saveSecondaryEvent({
        patientId,
        type: "symptom",
        title: formatted || "Unusual symptom",
        subtitle: `Patient observation${gStr}`,
        timestamp: `${date}T${time}:00Z`,
        details: { selectedSymptoms, nearbyGlucose, notes },
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["patient"] });
      options?.onSuccess?.();
    },
  });
}

/**
 * Saves a sleep duration event to local durable persistence.
 */
export function useSaveSleep(options?: { onSuccess?: () => void }) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      patientId,
      hours,
      minutes,
      quality,
      date,
      notes,
    }: {
      patientId: string;
      hours: number;
      minutes: number;
      quality: string;
      date: string;
      notes?: string;
    }) => {
      const qStr = quality.charAt(0).toUpperCase() + quality.slice(1);
      return await saveSecondaryEvent({
        patientId,
        type: "sleep",
        title: `${hours}h ${minutes > 0 ? `${minutes}m` : ""} sleep`,
        subtitle: `${qStr} quality`,
        timestamp: `${date}T08:00:00Z`,
        details: { hours, minutes, quality, notes },
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["patient"] });
      options?.onSuccess?.();
    },
  });
}

