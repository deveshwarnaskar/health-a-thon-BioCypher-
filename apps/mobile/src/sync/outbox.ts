import type { IDatabaseConnection } from "../db/database";
import type { LocalSessionContext } from "../db/isolation";

export type OutboxMutationType =
  | "INGEST_GLUCOSE"
  | "LOG_MEAL"
  | "START_TASK"
  | "COMPLETE_TASK"
  | "REASSIGN_TASK"
  | "CREATE_TASK";

export type OutboxStatus =
  | "PENDING"
  | "SYNCING"
  | "SYNCED"
  | "FAILED"
  | "CONFLICT"
  | "REQUIRES_ATTENTION";

export interface OutboxMutationRecord {
  id: string;
  seq?: number;
  tenantId: string;
  userId: string;
  mutationType: OutboxMutationType;
  endpoint: string;
  httpMethod: string;
  payloadJson: string;
  idempotencyKey: string;
  localEntityId: string | null;
  entityType: string;
  attemptCount: number;
  status: OutboxStatus;
  lastErrorCode: string | null;
  lastErrorMessage: string | null;
  nextRetryAt: string | null;
  createdAt: string;
  syncedAt: string | null;
}

export class MutationOutboxRepository {
  constructor(private readonly db: IDatabaseConnection) {}

  /**
   * Enqueues a mutation into the durable SQLite outbox.
   * MUST be called inside a local transaction alongside the local entity write.
   */
  async enqueue(record: Omit<OutboxMutationRecord, "seq" | "attemptCount" | "status" | "syncedAt">): Promise<void> {
    await this.db.runAsync(
      `INSERT INTO mutation_outbox (
        id, tenant_id, user_id, mutation_type, endpoint,
        http_method, payload_json, idempotency_key, local_entity_id,
        entity_type, attempt_count, status, last_error_code,
        last_error_message, next_retry_at, created_at, synced_at
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 'PENDING', NULL, NULL, NULL, ?, NULL)`,
      [
        record.id,
        record.tenantId,
        record.userId,
        record.mutationType,
        record.endpoint,
        record.httpMethod,
        record.payloadJson,
        record.idempotencyKey,
        record.localEntityId,
        record.entityType,
        record.createdAt,
      ]
    );
  }

  /**
   * Retrieves pending mutations for the authenticated user and tenant,
   * strictly ordered by sequence number and timestamp (deterministic FIFO).
   */
  async getPendingMutations(
    context: LocalSessionContext,
    options: { limit?: number; nowIso?: string } = {}
  ): Promise<OutboxMutationRecord[]> {
    const limit = options.limit ?? 50;
    const nowIso = options.nowIso ?? new Date().toISOString();

    const rows = await this.db.getAllAsync<any>(
      `SELECT * FROM mutation_outbox
       WHERE tenant_id = ? AND user_id = ?
         AND status IN ('PENDING', 'SYNCING')
         AND (next_retry_at IS NULL OR next_retry_at <= ?)
       ORDER BY seq ASC, created_at ASC
       LIMIT ?`,
      [context.tenantId, context.userId, nowIso, limit]
    );

    return rows.map(this.mapRow);
  }

  async markSyncing(id: string): Promise<void> {
    await this.db.runAsync(
      `UPDATE mutation_outbox SET status = 'SYNCING' WHERE id = ?`,
      [id]
    );
  }

  async markSynced(id: string, syncedAt: string): Promise<void> {
    await this.db.runAsync(
      `UPDATE mutation_outbox
       SET status = 'SYNCED', synced_at = ?
       WHERE id = ?`,
      [syncedAt, id]
    );
  }

  async markRetryable(
    id: string,
    nextRetryAt: string,
    errorCode: string | null,
    errorMessage: string | null
  ): Promise<void> {
    await this.db.runAsync(
      `UPDATE mutation_outbox
       SET status = 'PENDING',
           attempt_count = attempt_count + 1,
           next_retry_at = ?,
           last_error_code = ?,
           last_error_message = ?
       WHERE id = ?`,
      [nextRetryAt, errorCode, errorMessage, id]
    );
  }

  async markPermanentFailure(
    id: string,
    status: "FAILED" | "CONFLICT" | "REQUIRES_ATTENTION",
    errorCode: string | null,
    errorMessage: string | null
  ): Promise<void> {
    await this.db.runAsync(
      `UPDATE mutation_outbox
       SET status = ?,
           attempt_count = attempt_count + 1,
           last_error_code = ?,
           last_error_message = ?
       WHERE id = ?`,
      [status, errorCode, errorMessage, id]
    );
  }

  async getQueueDepth(context: LocalSessionContext): Promise<number> {
    const row = await this.db.getFirstAsync<{ count: number }>(
      `SELECT count(*) as count FROM mutation_outbox
       WHERE tenant_id = ? AND user_id = ? AND status IN ('PENDING', 'SYNCING')`,
      [context.tenantId, context.userId]
    );
    return row?.count ?? 0;
  }

  async findById(id: string): Promise<OutboxMutationRecord | null> {
    const row = await this.db.getFirstAsync<any>(
      `SELECT * FROM mutation_outbox WHERE id = ?`,
      [id]
    );
    return row ? this.mapRow(row) : null;
  }

  async findByIdempotencyKey(key: string): Promise<OutboxMutationRecord | null> {
    const row = await this.db.getFirstAsync<any>(
      `SELECT * FROM mutation_outbox WHERE idempotency_key = ?`,
      [key]
    );
    return row ? this.mapRow(row) : null;
  }

  private mapRow(row: any): OutboxMutationRecord {
    return {
      id: row.id,
      seq: row.seq,
      tenantId: row.tenant_id,
      userId: row.user_id,
      mutationType: row.mutation_type as OutboxMutationType,
      endpoint: row.endpoint,
      httpMethod: row.http_method,
      payloadJson: row.payload_json,
      idempotencyKey: row.idempotency_key,
      localEntityId: row.local_entity_id,
      entityType: row.entity_type,
      attemptCount: row.attempt_count,
      status: row.status as OutboxStatus,
      lastErrorCode: row.last_error_code,
      lastErrorMessage: row.last_error_message,
      nextRetryAt: row.next_retry_at,
      createdAt: row.created_at,
      syncedAt: row.synced_at,
    };
  }
}
