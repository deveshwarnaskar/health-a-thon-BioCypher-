import { sqliteTable, text, integer, real, index } from "drizzle-orm/sqlite-core";

/**
 * App Metadata / Versioning Table
 */
export const appMeta = sqliteTable("app_meta", {
  key: text("key").primaryKey(),
  value: text("value").notNull(),
  updatedAt: text("updated_at").notNull(),
});

/**
 * Local Patients Projection (Read-only cache)
 */
export const localPatients = sqliteTable(
  "local_patients",
  {
    id: text("id").primaryKey(),
    tenantId: text("tenant_id").notNull(),
    userId: text("user_id").notNull(),
    fullName: text("full_name").notNull(),
    birthDate: text("birth_date"),
    status: text("status").notNull(),
    syncedAt: text("synced_at").notNull(),
  },
  (table) => [
    index("idx_patients_tenant_user").on(table.tenantId, table.userId),
  ]
);

/**
 * Local Glucose Observations
 */
export const localGlucoseObservations = sqliteTable(
  "local_glucose_observations",
  {
    localId: text("local_id").primaryKey(),
    serverId: text("server_id"),
    tenantId: text("tenant_id").notNull(),
    userId: text("user_id").notNull(),
    patientId: text("patient_id").notNull(),
    valueMgDl: integer("value_mg_dl").notNull(),
    tag: text("tag"),
    takenAt: text("taken_at").notNull(),
    syncStatus: text("sync_status").notNull(), // 'SAVED_LOCALLY' | 'WAITING_TO_SYNC' | 'SYNCING' | 'SYNCED' | 'NEEDS_ATTENTION'
    idempotencyKey: text("idempotency_key").notNull(),
    createdAt: text("created_at").notNull(),
    syncedAt: text("synced_at"),
  },
  (table) => [
    index("idx_glucose_tenant_user_patient").on(table.tenantId, table.userId, table.patientId),
    index("idx_glucose_sync_status").on(table.syncStatus),
  ]
);

/**
 * Local Meals
 */
export const localMeals = sqliteTable(
  "local_meals",
  {
    localId: text("local_id").primaryKey(),
    serverId: text("server_id"),
    tenantId: text("tenant_id").notNull(),
    userId: text("user_id").notNull(),
    patientId: text("patient_id").notNull(),
    description: text("description").notNull(),
    portionSize: text("portion_size"),
    portionCount: real("portion_count"),
    portionGrams: real("portion_grams"),
    recordedAt: text("recorded_at").notNull(),
    syncStatus: text("sync_status").notNull(),
    idempotencyKey: text("idempotency_key").notNull(),
    createdAt: text("created_at").notNull(),
    syncedAt: text("synced_at"),
  },
  (table) => [
    index("idx_meals_tenant_user_patient").on(table.tenantId, table.userId, table.patientId),
    index("idx_meals_sync_status").on(table.syncStatus),
  ]
);

/**
 * Local Care Tasks
 */
export const localCareTasks = sqliteTable(
  "local_care_tasks",
  {
    localId: text("local_id").primaryKey(),
    serverId: text("server_id").notNull(),
    tenantId: text("tenant_id").notNull(),
    userId: text("user_id").notNull(),
    patientId: text("patient_id").notNull(),
    title: text("title").notNull(),
    description: text("description"),
    taskType: text("task_type").notNull(),
    status: text("status").notNull(), // 'OPEN' | 'IN_PROGRESS' | 'COMPLETED'
    priority: text("priority").notNull(),
    dueDate: text("due_date"),
    syncStatus: text("sync_status").notNull(),
    createdAt: text("created_at").notNull(),
    updatedAt: text("updated_at").notNull(),
  },
  (table) => [
    index("idx_care_tasks_tenant_user").on(table.tenantId, table.userId),
    index("idx_care_tasks_server_id").on(table.serverId),
  ]
);

/**
 * Local Notifications Projection
 */
export const localNotifications = sqliteTable(
  "local_notifications",
  {
    id: text("id").primaryKey(),
    tenantId: text("tenant_id").notNull(),
    userId: text("user_id").notNull(),
    title: text("title").notNull(),
    body: text("body").notNull(),
    createdAt: text("created_at").notNull(),
    readAt: text("read_at"),
  },
  (table) => [
    index("idx_notifications_tenant_user").on(table.tenantId, table.userId),
  ]
);

/**
 * Local Document Metadata (Strictly scoped metadata only, no raw unrestricted reports)
 */
export const localDocuments = sqliteTable(
  "local_documents",
  {
    id: text("id").primaryKey(),
    tenantId: text("tenant_id").notNull(),
    userId: text("user_id").notNull(),
    patientId: text("patient_id").notNull(),
    kind: text("kind").notNull(),
    filename: text("filename").notNull(),
    fileSizeBytes: integer("file_size_bytes").notNull(),
    contentType: text("content_type").notNull(),
    createdAt: text("created_at").notNull(),
  },
  (table) => [
    index("idx_documents_tenant_user").on(table.tenantId, table.userId),
  ]
);

/**
 * Durable Client Mutation Outbox
 */
export const mutationOutbox = sqliteTable(
  "mutation_outbox",
  {
    id: text("id").notNull().unique(),
    seq: integer("seq").primaryKey({ autoIncrement: true }),
    tenantId: text("tenant_id").notNull(),
    userId: text("user_id").notNull(),
    mutationType: text("mutation_type").notNull(), // 'INGEST_GLUCOSE' | 'LOG_MEAL' | 'START_TASK' | 'COMPLETE_TASK' | 'REASSIGN_TASK' | 'CREATE_TASK'
    endpoint: text("endpoint").notNull(),
    httpMethod: text("http_method").notNull(),
    payloadJson: text("payload_json").notNull(),
    idempotencyKey: text("idempotency_key").notNull(),
    localEntityId: text("local_entity_id"),
    entityType: text("entity_type").notNull(),
    attemptCount: integer("attempt_count").notNull().default(0),
    status: text("status").notNull(), // 'PENDING' | 'SYNCING' | 'SYNCED' | 'FAILED' | 'CONFLICT' | 'REQUIRES_ATTENTION'
    lastErrorCode: text("last_error_code"),
    lastErrorMessage: text("last_error_message"),
    nextRetryAt: text("next_retry_at"),
    createdAt: text("created_at").notNull(),
    syncedAt: text("synced_at"),
  },
  (table) => [
    index("idx_outbox_tenant_user_status").on(table.tenantId, table.userId, table.status),
    index("idx_outbox_seq").on(table.seq),
    index("idx_outbox_idempotency_key").on(table.idempotencyKey),
  ]
);
