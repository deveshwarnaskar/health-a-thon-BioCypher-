import type { IDatabaseConnection } from "./database";
import type { LocalSessionContext } from "./isolation";

export type SyncStatus =
  | "SAVED_LOCALLY"
  | "WAITING_TO_SYNC"
  | "SYNCING"
  | "SYNCED"
  | "NEEDS_ATTENTION";

export interface LocalGlucoseRecord {
  localId: string;
  serverId: string | null;
  tenantId: string;
  userId: string;
  patientId: string;
  valueMgDl: number;
  tag: string | null;
  takenAt: string;
  syncStatus: SyncStatus;
  idempotencyKey: string;
  createdAt: string;
  syncedAt: string | null;
}

export interface LocalMealRecord {
  localId: string;
  serverId: string | null;
  tenantId: string;
  userId: string;
  patientId: string;
  description: string;
  portionSize: string | null;
  portionCount: number | null;
  portionGrams: number | null;
  recordedAt: string;
  syncStatus: SyncStatus;
  idempotencyKey: string;
  createdAt: string;
  syncedAt: string | null;
}

export interface LocalCareTaskRecord {
  localId: string;
  serverId: string;
  tenantId: string;
  userId: string;
  patientId: string;
  title: string;
  description: string | null;
  taskType: string;
  status: "OPEN" | "IN_PROGRESS" | "COMPLETED";
  priority: string;
  dueDate: string | null;
  syncStatus: SyncStatus;
  createdAt: string;
  updatedAt: string;
}

export class GlucoseRepository {
  constructor(private readonly db: IDatabaseConnection) {}

  async insert(record: LocalGlucoseRecord): Promise<void> {
    await this.db.runAsync(
      `INSERT INTO local_glucose_observations (
        local_id, server_id, tenant_id, user_id, patient_id,
        value_mg_dl, tag, taken_at, sync_status, idempotency_key,
        created_at, synced_at
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [
        record.localId,
        record.serverId,
        record.tenantId,
        record.userId,
        record.patientId,
        record.valueMgDl,
        record.tag,
        record.takenAt,
        record.syncStatus,
        record.idempotencyKey,
        record.createdAt,
        record.syncedAt,
      ]
    );
  }

  async findByPatient(
    context: LocalSessionContext,
    patientId: string
  ): Promise<LocalGlucoseRecord[]> {
    const rows = await this.db.getAllAsync<any>(
      `SELECT * FROM local_glucose_observations
       WHERE tenant_id = ? AND user_id = ? AND patient_id = ?
       ORDER BY taken_at DESC`,
      [context.tenantId, context.userId, patientId]
    );
    return rows.map(this.mapRow);
  }

  async findById(localId: string): Promise<LocalGlucoseRecord | null> {
    const row = await this.db.getFirstAsync<any>(
      `SELECT * FROM local_glucose_observations WHERE local_id = ?`,
      [localId]
    );
    return row ? this.mapRow(row) : null;
  }

  async markSynced(localId: string, serverId: string, syncedAt: string): Promise<void> {
    await this.db.runAsync(
      `UPDATE local_glucose_observations
       SET server_id = ?, sync_status = 'SYNCED', synced_at = ?
       WHERE local_id = ?`,
      [serverId, syncedAt, localId]
    );
  }

  async markStatus(localId: string, status: SyncStatus): Promise<void> {
    await this.db.runAsync(
      `UPDATE local_glucose_observations SET sync_status = ? WHERE local_id = ?`,
      [status, localId]
    );
  }

  private mapRow(row: any): LocalGlucoseRecord {
    return {
      localId: row.local_id,
      serverId: row.server_id,
      tenantId: row.tenant_id,
      userId: row.user_id,
      patientId: row.patient_id,
      valueMgDl: row.value_mg_dl,
      tag: row.tag,
      takenAt: row.taken_at,
      syncStatus: row.sync_status as SyncStatus,
      idempotencyKey: row.idempotency_key,
      createdAt: row.created_at,
      syncedAt: row.synced_at,
    };
  }
}

export class MealRepository {
  constructor(private readonly db: IDatabaseConnection) {}

  async insert(record: LocalMealRecord): Promise<void> {
    await this.db.runAsync(
      `INSERT INTO local_meals (
        local_id, server_id, tenant_id, user_id, patient_id,
        description, portion_size, portion_count, portion_grams,
        recorded_at, sync_status, idempotency_key, created_at, synced_at
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [
        record.localId,
        record.serverId,
        record.tenantId,
        record.userId,
        record.patientId,
        record.description,
        record.portionSize,
        record.portionCount,
        record.portionGrams,
        record.recordedAt,
        record.syncStatus,
        record.idempotencyKey,
        record.createdAt,
        record.syncedAt,
      ]
    );
  }

  async findByPatient(
    context: LocalSessionContext,
    patientId: string
  ): Promise<LocalMealRecord[]> {
    const rows = await this.db.getAllAsync<any>(
      `SELECT * FROM local_meals
       WHERE tenant_id = ? AND user_id = ? AND patient_id = ?
       ORDER BY recorded_at DESC`,
      [context.tenantId, context.userId, patientId]
    );
    return rows.map(this.mapRow);
  }

  async markSynced(localId: string, serverId: string, syncedAt: string): Promise<void> {
    await this.db.runAsync(
      `UPDATE local_meals
       SET server_id = ?, sync_status = 'SYNCED', synced_at = ?
       WHERE local_id = ?`,
      [serverId, syncedAt, localId]
    );
  }

  async markStatus(localId: string, status: SyncStatus): Promise<void> {
    await this.db.runAsync(
      `UPDATE local_meals SET sync_status = ? WHERE local_id = ?`,
      [status, localId]
    );
  }

  private mapRow(row: any): LocalMealRecord {
    return {
      localId: row.local_id,
      serverId: row.server_id,
      tenantId: row.tenant_id,
      userId: row.user_id,
      patientId: row.patient_id,
      description: row.description,
      portionSize: row.portion_size,
      portionCount: row.portion_count,
      portionGrams: row.portion_grams,
      recordedAt: row.recorded_at,
      syncStatus: row.sync_status as SyncStatus,
      idempotencyKey: row.idempotency_key,
      createdAt: row.created_at,
      syncedAt: row.synced_at,
    };
  }
}

export class CareTaskRepository {
  constructor(private readonly db: IDatabaseConnection) {}

  async upsert(record: LocalCareTaskRecord): Promise<void> {
    await this.db.runAsync(
      `INSERT OR REPLACE INTO local_care_tasks (
        local_id, server_id, tenant_id, user_id, patient_id,
        title, description, task_type, status, priority,
        due_date, sync_status, created_at, updated_at
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [
        record.localId,
        record.serverId,
        record.tenantId,
        record.userId,
        record.patientId,
        record.title,
        record.description,
        record.taskType,
        record.status,
        record.priority,
        record.dueDate,
        record.syncStatus,
        record.createdAt,
        record.updatedAt,
      ]
    );
  }

  async list(context: LocalSessionContext): Promise<LocalCareTaskRecord[]> {
    const rows = await this.db.getAllAsync<any>(
      `SELECT * FROM local_care_tasks
       WHERE tenant_id = ? AND user_id = ?
       ORDER BY created_at DESC`,
      [context.tenantId, context.userId]
    );
    return rows.map(this.mapRow);
  }

  async findByServerId(serverId: string): Promise<LocalCareTaskRecord | null> {
    const row = await this.db.getFirstAsync<any>(
      `SELECT * FROM local_care_tasks WHERE server_id = ?`,
      [serverId]
    );
    return row ? this.mapRow(row) : null;
  }

  async updateLocalStatus(
    serverId: string,
    status: "OPEN" | "IN_PROGRESS" | "COMPLETED",
    syncStatus: SyncStatus,
    updatedAt: string
  ): Promise<void> {
    await this.db.runAsync(
      `UPDATE local_care_tasks
       SET status = ?, sync_status = ?, updated_at = ?
       WHERE server_id = ?`,
      [status, syncStatus, updatedAt, serverId]
    );
  }

  private mapRow(row: any): LocalCareTaskRecord {
    return {
      localId: row.local_id,
      serverId: row.server_id,
      tenantId: row.tenant_id,
      userId: row.user_id,
      patientId: row.patient_id,
      title: row.title,
      description: row.description,
      taskType: row.task_type,
      status: row.status,
      priority: row.priority,
      dueDate: row.due_date,
      syncStatus: row.sync_status as SyncStatus,
      createdAt: row.created_at,
      updatedAt: row.updated_at,
    };
  }
}
