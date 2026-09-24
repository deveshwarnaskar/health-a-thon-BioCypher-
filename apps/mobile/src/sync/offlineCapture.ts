import type { IDatabaseConnection } from "../db/database";
import type { LocalSessionContext } from "../db/isolation";
import { MutationOutboxRepository } from "./outbox";
import {
  GlucoseRepository,
  MealRepository,
  CareTaskRepository,
} from "../db/repositories";
import { secureUuid } from "../services/api/correlation";
import type { IngestGlucoseRequest, IngestGlucoseResponse } from "../services/schemas/clinical";
import type { LogMealRequest, LogMealResponse } from "../services/schemas/meals";

export interface OfflineGlucoseCaptureResult extends IngestGlucoseResponse {
  sync_status: "SAVED_LOCALLY";
  local_id: string;
}

export interface OfflineMealCaptureResult extends LogMealResponse {
  sync_status: "SAVED_LOCALLY";
  local_id: string;
}

export class OfflineCaptureService {
  private readonly outboxRepo: MutationOutboxRepository;
  private readonly glucoseRepo: GlucoseRepository;
  private readonly mealRepo: MealRepository;
  private readonly taskRepo: CareTaskRepository;

  constructor(private readonly db: IDatabaseConnection) {
    this.outboxRepo = new MutationOutboxRepository(this.db);
    this.glucoseRepo = new GlucoseRepository(this.db);
    this.mealRepo = new MealRepository(this.db);
    this.taskRepo = new CareTaskRepository(this.db);
  }

  /**
   * Captures a glucose observation into encrypted local persistence and outbox atomically.
   * Preserves the logical Idempotency-Key.
   */
  async captureGlucose(
    context: LocalSessionContext,
    request: IngestGlucoseRequest,
    idempotencyKey: string
  ): Promise<OfflineGlucoseCaptureResult> {
    const localId = secureUuid();
    const nowIso = new Date().toISOString();
    const takenAt = request.taken_at ?? nowIso;

    await this.db.withTransactionAsync(async () => {
      // 1. Insert local observation
      await this.glucoseRepo.insert({
        localId,
        serverId: null,
        tenantId: context.tenantId,
        userId: context.userId,
        patientId: request.patient_id,
        valueMgDl: request.value_mg_dl,
        tag: request.tag ?? null,
        takenAt,
        syncStatus: "SAVED_LOCALLY",
        idempotencyKey,
        createdAt: nowIso,
        syncedAt: null,
      });

      // 2. Enqueue in durable mutation outbox
      await this.outboxRepo.enqueue({
        id: secureUuid(),
        tenantId: context.tenantId,
        userId: context.userId,
        mutationType: "INGEST_GLUCOSE",
        endpoint: "/api/v2/clinical/observations",
        httpMethod: "POST",
        payloadJson: JSON.stringify(request),
        idempotencyKey,
        localEntityId: localId,
        entityType: "glucose",
        lastErrorCode: null,
        lastErrorMessage: null,
        nextRetryAt: null,
        createdAt: nowIso,
      });
    });

    return {
      observation_id: localId,
      local_id: localId,
      patient_id: request.patient_id,
      value_mg_dl: request.value_mg_dl,
      taken_at: takenAt,
      sync_status: "SAVED_LOCALLY",
    };
  }

  /**
   * Captures a meal draft into encrypted local persistence and outbox atomically.
   */
  async captureMeal(
    context: LocalSessionContext,
    request: LogMealRequest,
    idempotencyKey: string
  ): Promise<OfflineMealCaptureResult> {
    const localId = secureUuid();
    const nowIso = new Date().toISOString();
    const recordedAt = request.recorded_at ?? nowIso;

    await this.db.withTransactionAsync(async () => {
      // 1. Insert local meal record
      await this.mealRepo.insert({
        localId,
        serverId: null,
        tenantId: context.tenantId,
        userId: context.userId,
        patientId: request.patient_id,
        description: request.description,
        portionSize: request.portion?.food_key ?? null,
        portionCount: request.portion?.quantity ?? null,
        portionGrams: null,
        recordedAt,
        syncStatus: "SAVED_LOCALLY",
        idempotencyKey,
        createdAt: nowIso,
        syncedAt: null,
      });

      // 2. Enqueue in durable mutation outbox
      await this.outboxRepo.enqueue({
        id: secureUuid(),
        tenantId: context.tenantId,
        userId: context.userId,
        mutationType: "LOG_MEAL",
        endpoint: "/api/v2/clinical/meals",
        httpMethod: "POST",
        payloadJson: JSON.stringify(request),
        idempotencyKey,
        localEntityId: localId,
        entityType: "meal",
        lastErrorCode: null,
        lastErrorMessage: null,
        nextRetryAt: null,
        createdAt: nowIso,
      });
    });

    return {
      meal_observation_id: localId,
      local_id: localId,
      patient_id: request.patient_id,
      portion_label: request.portion ? `${request.portion.quantity}x` : null,
      quantity: request.portion?.quantity ?? null,
      sync_status: "SAVED_LOCALLY",
    };
  }

  /**
   * Captures an offline task status mutation (START or COMPLETE).
   */
  async captureTaskTransition(
    context: LocalSessionContext,
    taskId: string,
    action: "START" | "COMPLETE",
    idempotencyKey: string
  ): Promise<{ taskId: string; status: "IN_PROGRESS" | "COMPLETED"; sync_status: "WAITING_TO_SYNC" }> {
    const nowIso = new Date().toISOString();
    const newStatus = action === "START" ? "IN_PROGRESS" : "COMPLETED";
    const mutationType = action === "START" ? "START_TASK" : "COMPLETE_TASK";
    const endpoint = `/api/v2/care-tasks/${encodeURIComponent(taskId)}/${action.toLowerCase()}`;

    await this.db.withTransactionAsync(async () => {
      await this.taskRepo.updateLocalStatus(taskId, newStatus, "WAITING_TO_SYNC", nowIso);

      await this.outboxRepo.enqueue({
        id: secureUuid(),
        tenantId: context.tenantId,
        userId: context.userId,
        mutationType,
        endpoint,
        httpMethod: "POST",
        payloadJson: JSON.stringify({}),
        idempotencyKey,
        localEntityId: taskId,
        entityType: "care_task",
        lastErrorCode: null,
        lastErrorMessage: null,
        nextRetryAt: null,
        createdAt: nowIso,
      });
    });

    return {
      taskId,
      status: newStatus,
      sync_status: "WAITING_TO_SYNC",
    };
  }

  /**
   * Captures an offline medication administration (adherence) event into the outbox.
   * Section 4.1.C & Section 30: Preserves idempotency key and offline state.
   */
  async captureMedicationAdministration(
    context: LocalSessionContext,
    medicationPlanId: string,
    administeredAt: string,
    idempotencyKey: string
  ): Promise<{
    medication_plan_id: string;
    patient_id: string;
    administered_at: string;
    sync_status: "SAVED_LOCALLY";
  }> {
    const localId = secureUuid();
    const nowIso = new Date().toISOString();

    await this.outboxRepo.enqueue({
      id: secureUuid(),
      tenantId: context.tenantId,
      userId: context.userId,
      mutationType: "ADMINISTER_MEDICATION",
      endpoint: "/api/v2/clinical/medication-administrations",
      httpMethod: "POST",
      payloadJson: JSON.stringify({
        medication_plan_id: medicationPlanId,
        administered_at: administeredAt,
      }),
      idempotencyKey,
      localEntityId: localId,
      entityType: "medication_administration",
      lastErrorCode: null,
      lastErrorMessage: null,
      nextRetryAt: null,
      createdAt: nowIso,
    });

    return {
      medication_plan_id: medicationPlanId,
      patient_id: context.patientId ?? context.userId,
      administered_at: administeredAt,
      sync_status: "SAVED_LOCALLY",
    };
  }

  /**
   * Captures an offline document upload into local metadata table and outbox.
   * Section 8 & Section 30: Document is queued locally and synced when online.
   */
  async captureDocumentUpload(
    context: LocalSessionContext,
    patientId: string,
    document: {
      filename: string;
      mime_type: string;
      content_base64: string;
      kind?: string;
    },
    idempotencyKey: string
  ): Promise<{
    id: string;
    filename: string;
    kind: string;
    sync_status: "SAVED_LOCALLY";
  }> {
    const localId = secureUuid();
    const nowIso = new Date().toISOString();
    const kind = document.kind ?? "chart_image";
    const approxBytes = Math.round((document.content_base64.length * 3) / 4);

    await this.db.withTransactionAsync(async () => {
      // 1. Cache metadata locally in local_documents
      await this.db.runAsync(
        `INSERT INTO local_documents (
          id, tenant_id, user_id, patient_id, kind, filename, file_size_bytes, content_type, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        [
          localId,
          context.tenantId,
          context.userId,
          patientId,
          kind,
          document.filename,
          approxBytes,
          document.mime_type,
          nowIso,
        ]
      );

      // 2. Enqueue in mutation outbox
      await this.outboxRepo.enqueue({
        id: secureUuid(),
        tenantId: context.tenantId,
        userId: context.userId,
        mutationType: "UPLOAD_DOCUMENT",
        endpoint: `/api/v2/clinical/patients/${encodeURIComponent(patientId)}/documents/upload`,
        httpMethod: "POST",
        payloadJson: JSON.stringify(document),
        idempotencyKey,
        localEntityId: localId,
        entityType: "document",
        lastErrorCode: null,
        lastErrorMessage: null,
        nextRetryAt: null,
        createdAt: nowIso,
      });
    });

    return {
      id: localId,
      filename: document.filename,
      kind,
      sync_status: "SAVED_LOCALLY",
    };
  }
}
