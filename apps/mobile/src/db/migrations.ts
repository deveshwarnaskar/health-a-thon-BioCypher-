export interface MigrationDb {
  execAsync(sql: string): Promise<void>;
  getFirstAsync<T>(sql: string, params?: unknown[]): Promise<T | null>;
}

export const CURRENT_SCHEMA_VERSION = 1;

export const INITIAL_MIGRATION_SQL = `
CREATE TABLE IF NOT EXISTS app_meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS local_patients (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  full_name TEXT NOT NULL,
  birth_date TEXT,
  status TEXT NOT NULL,
  synced_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_patients_tenant_user ON local_patients(tenant_id, user_id);

CREATE TABLE IF NOT EXISTS local_glucose_observations (
  local_id TEXT PRIMARY KEY,
  server_id TEXT,
  tenant_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  patient_id TEXT NOT NULL,
  value_mg_dl INTEGER NOT NULL,
  tag TEXT,
  taken_at TEXT NOT NULL,
  sync_status TEXT NOT NULL,
  idempotency_key TEXT NOT NULL,
  created_at TEXT NOT NULL,
  synced_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_glucose_tenant_user_patient ON local_glucose_observations(tenant_id, user_id, patient_id);
CREATE INDEX IF NOT EXISTS idx_glucose_sync_status ON local_glucose_observations(sync_status);

CREATE TABLE IF NOT EXISTS local_meals (
  local_id TEXT PRIMARY KEY,
  server_id TEXT,
  tenant_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  patient_id TEXT NOT NULL,
  description TEXT NOT NULL,
  portion_size TEXT,
  portion_count REAL,
  portion_grams REAL,
  recorded_at TEXT NOT NULL,
  sync_status TEXT NOT NULL,
  idempotency_key TEXT NOT NULL,
  created_at TEXT NOT NULL,
  synced_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_meals_tenant_user_patient ON local_meals(tenant_id, user_id, patient_id);
CREATE INDEX IF NOT EXISTS idx_meals_sync_status ON local_meals(sync_status);

CREATE TABLE IF NOT EXISTS local_care_tasks (
  local_id TEXT PRIMARY KEY,
  server_id TEXT NOT NULL,
  tenant_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  patient_id TEXT NOT NULL,
  title TEXT NOT NULL,
  description TEXT,
  task_type TEXT NOT NULL,
  status TEXT NOT NULL,
  priority TEXT NOT NULL,
  due_date TEXT,
  sync_status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_care_tasks_tenant_user ON local_care_tasks(tenant_id, user_id);
CREATE INDEX IF NOT EXISTS idx_care_tasks_server_id ON local_care_tasks(server_id);

CREATE TABLE IF NOT EXISTS local_notifications (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  created_at TEXT NOT NULL,
  read_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_notifications_tenant_user ON local_notifications(tenant_id, user_id);

CREATE TABLE IF NOT EXISTS local_documents (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  patient_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  filename TEXT NOT NULL,
  file_size_bytes INTEGER NOT NULL,
  content_type TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_documents_tenant_user ON local_documents(tenant_id, user_id);

CREATE TABLE IF NOT EXISTS mutation_outbox (
  id TEXT PRIMARY KEY,
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  mutation_type TEXT NOT NULL,
  endpoint TEXT NOT NULL,
  http_method TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  idempotency_key TEXT NOT NULL,
  local_entity_id TEXT,
  entity_type TEXT NOT NULL,
  attempt_count INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL,
  last_error_code TEXT,
  last_error_message TEXT,
  next_retry_at TEXT,
  created_at TEXT NOT NULL,
  synced_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_outbox_tenant_user_status ON mutation_outbox(tenant_id, user_id, status);
CREATE INDEX IF NOT EXISTS idx_outbox_idempotency_key ON mutation_outbox(idempotency_key);
`;

export async function runLocalMigrations(db: MigrationDb): Promise<void> {
  // Check if app_meta table exists
  let currentVersion = 0;
  try {
    const metaRow = await db.getFirstAsync<{ value: string }>(
      "SELECT value FROM app_meta WHERE key = 'schema_version'"
    );
    if (metaRow?.value) {
      currentVersion = parseInt(metaRow.value, 10) || 0;
    }
  } catch {
    // Table doesn't exist yet, version is 0
    currentVersion = 0;
  }

  if (currentVersion === 0) {
    await db.execAsync(INITIAL_MIGRATION_SQL);
    await db.execAsync(`
      INSERT OR REPLACE INTO app_meta (key, value, updated_at)
      VALUES ('schema_version', '1', datetime('now'));
    `);
    currentVersion = 1;
  }

  if (currentVersion < CURRENT_SCHEMA_VERSION) {
    // Future incremental migrations go here
  }
}
