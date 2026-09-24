import type { ApiClient } from "../services/api/client";
import type { IDatabaseConnection } from "../db/database";
import type { LocalSessionContext } from "../db/isolation";
import { MutationOutboxRepository, type OutboxMutationRecord } from "./outbox";
import {
  GlucoseRepository,
  MealRepository,
  CareTaskRepository,
} from "../db/repositories";
import { classifySyncError } from "./retryPolicy";

export type SyncTelemetryEvent =
  | { event: "sync_started"; queueDepth: number; tenantId: string }
  | { event: "sync_completed"; processedCount: number; remainingCount: number }
  | { event: "sync_failed"; error: string; code: string }
  | { event: "mutation_synced"; mutationId: string; mutationType: string }
  | { event: "mutation_retryable"; mutationId: string; attemptCount: number; delayMs: number }
  | { event: "mutation_permanent_failure"; mutationId: string; code: string }
  | { event: "mutation_conflict"; mutationId: string; code: string };

export type TelemetryListener = (event: SyncTelemetryEvent) => void;

export interface SyncCoordinatorDependencies {
  db: IDatabaseConnection;
  apiClient: ApiClient;
  onTelemetry?: TelemetryListener;
}

export class SyncCoordinator {
  private readonly db: IDatabaseConnection;
  private readonly apiClient: ApiClient;
  private readonly outboxRepo: MutationOutboxRepository;
  private readonly glucoseRepo: GlucoseRepository;
  private readonly mealRepo: MealRepository;
  private readonly taskRepo: CareTaskRepository;
  private readonly telemetryListeners = new Set<TelemetryListener>();

  private isSyncing = false;
  private activeSyncPromise: Promise<{ processed: number; failed: number }> | null = null;

  constructor(deps: SyncCoordinatorDependencies) {
    this.db = deps.db;
    this.apiClient = deps.apiClient;
    this.outboxRepo = new MutationOutboxRepository(this.db);
    this.glucoseRepo = new GlucoseRepository(this.db);
    this.mealRepo = new MealRepository(this.db);
    this.taskRepo = new CareTaskRepository(this.db);
    if (deps.onTelemetry) {
      this.telemetryListeners.add(deps.onTelemetry);
    }
  }

  addTelemetryListener(listener: TelemetryListener): () => void {
    this.telemetryListeners.add(listener);
    return () => this.telemetryListeners.delete(listener);
  }

  private emitTelemetry(event: SyncTelemetryEvent): void {
    for (const listener of this.telemetryListeners) {
      try {
        listener(event);
      } catch {
        // Telemetry errors must never abort sync
      }
    }
  }

  /**
   * Main sync trigger.
   * Concurrency Safe: If a sync is already in progress, joins the active promise.
   * Returns summary of processed and failed mutations.
   */
  async sync(context: LocalSessionContext): Promise<{ processed: number; failed: number }> {
    if (this.isSyncing && this.activeSyncPromise) {
      return this.activeSyncPromise;
    }

    this.isSyncing = true;
    this.activeSyncPromise = this.executeSync(context).finally(() => {
      this.isSyncing = false;
      this.activeSyncPromise = null;
    });

    return this.activeSyncPromise;
  }

  private async executeSync(
    context: LocalSessionContext
  ): Promise<{ processed: number; failed: number }> {
    const queueDepth = await this.outboxRepo.getQueueDepth(context);
    this.emitTelemetry({
      event: "sync_started",
      queueDepth,
      tenantId: context.tenantId,
    });

    let processed = 0;
    let failed = 0;

    const pending = await this.outboxRepo.getPendingMutations(context);
    for (const mutation of pending) {
      const outcome = await this.processMutation(context, mutation);
      if (outcome.success) {
        processed++;
      } else {
        failed++;
        if (outcome.authExpired) {
          // Authentication expired and refresh failed; stop sync pipeline immediately
          break;
        }
      }
    }

    const remaining = await this.outboxRepo.getQueueDepth(context);
    this.emitTelemetry({
      event: "sync_completed",
      processedCount: processed,
      remainingCount: remaining,
    });

    return { processed, failed };
  }

  private async processMutation(
    context: LocalSessionContext,
    mutation: OutboxMutationRecord
  ): Promise<{ success: boolean; authExpired?: boolean }> {
    await this.outboxRepo.markSyncing(mutation.id);

    try {
      const payload = JSON.parse(mutation.payloadJson);

      // Submit via ApiClient.
      // INVARIANT: Exactly identical Idempotency-Key is preserved across every retry.
      const response = await this.apiClient.request<any>({
        method: mutation.httpMethod as any,
        path: mutation.endpoint,
        body: payload,
        idempotencyKey: mutation.idempotencyKey,
      });

      const nowIso = new Date().toISOString();
      const serverId = response?.id ?? response?.observation_id ?? response?.data?.id ?? null;

      // 1. Reconcile local state with authoritative server response
      await this.reconcileLocalEntitySuccess(mutation, serverId, nowIso);

      // 2. Mark outbox mutation as SYNCED
      await this.outboxRepo.markSynced(mutation.id, nowIso);

      this.emitTelemetry({
        event: "mutation_synced",
        mutationId: mutation.id,
        mutationType: mutation.mutationType,
      });

      return { success: true };
    } catch (error: any) {
      const classification = classifySyncError(error, mutation.attemptCount);

      if (classification.outcome === "RETRYABLE") {
        const nextRetryAt = new Date(Date.now() + classification.delayMs).toISOString();
        await this.outboxRepo.markRetryable(
          mutation.id,
          nextRetryAt,
          classification.code,
          classification.message
        );
        if (mutation.localEntityId) {
          await this.setLocalEntityStatus(mutation, "WAITING_TO_SYNC");
        }
        this.emitTelemetry({
          event: "mutation_retryable",
          mutationId: mutation.id,
          attemptCount: mutation.attemptCount + 1,
          delayMs: classification.delayMs,
        });
        return { success: false };
      }

      if (classification.outcome === "AUTH_EXPIRED") {
        // Surrender outbox item back to PENDING so user can re-authenticate
        await this.outboxRepo.markRetryable(
          mutation.id,
          new Date(Date.now() + 5000).toISOString(),
          classification.code,
          classification.message
        );
        return { success: false, authExpired: true };
      }

      if (classification.outcome === "CONFLICT") {
        await this.outboxRepo.markPermanentFailure(
          mutation.id,
          "CONFLICT",
          classification.code,
          classification.message
        );
        if (mutation.localEntityId) {
          await this.setLocalEntityStatus(mutation, "NEEDS_ATTENTION");
        }
        this.emitTelemetry({
          event: "mutation_conflict",
          mutationId: mutation.id,
          code: classification.code,
        });
        return { success: false };
      }

      // PERMANENT_REJECTION (403 forbidden, 404 not found, 422 unprocessable)
      await this.outboxRepo.markPermanentFailure(
        mutation.id,
        "FAILED",
        classification.code,
        classification.message
      );
      if (mutation.localEntityId) {
        await this.setLocalEntityStatus(mutation, "NEEDS_ATTENTION");
      }
      this.emitTelemetry({
        event: "mutation_permanent_failure",
        mutationId: mutation.id,
        code: classification.code,
      });

      return { success: false };
    }
  }

  private async reconcileLocalEntitySuccess(
    mutation: OutboxMutationRecord,
    serverId: string | null,
    nowIso: string
  ): Promise<void> {
    if (!mutation.localEntityId) return;

    if (mutation.entityType === "glucose") {
      await this.glucoseRepo.markSynced(mutation.localEntityId, serverId ?? mutation.localEntityId, nowIso);
    } else if (mutation.entityType === "meal") {
      await this.mealRepo.markSynced(mutation.localEntityId, serverId ?? mutation.localEntityId, nowIso);
    } else if (mutation.entityType === "care_task") {
      const task = await this.taskRepo.findByServerId(mutation.localEntityId);
      if (task) {
        let newStatus = task.status;
        if (mutation.mutationType === "START_TASK") newStatus = "IN_PROGRESS";
        if (mutation.mutationType === "COMPLETE_TASK") newStatus = "COMPLETED";
        await this.taskRepo.updateLocalStatus(mutation.localEntityId, newStatus, "SYNCED", nowIso);
      }
    } else if (mutation.entityType === "document") {
      await this.db.runAsync("DELETE FROM local_documents WHERE id = ?", [mutation.localEntityId]).catch(() => {});
    }
  }

  private async setLocalEntityStatus(
    mutation: OutboxMutationRecord,
    status: "WAITING_TO_SYNC" | "NEEDS_ATTENTION"
  ): Promise<void> {
    if (!mutation.localEntityId) return;

    if (mutation.entityType === "glucose") {
      await this.glucoseRepo.markStatus(mutation.localEntityId, status);
    } else if (mutation.entityType === "meal") {
      await this.mealRepo.markStatus(mutation.localEntityId, status);
    }
  }
}
