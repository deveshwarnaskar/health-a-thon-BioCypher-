import type { IDatabaseConnection } from "../../../src/db/database";

interface TableStore {
  rows: Record<string, any>[];
  autoInc: number;
}

export class MockSqlCipherDatabase implements IDatabaseConnection {
  private tables: Map<string, TableStore> = new Map();
  private encryptionKey: string | null = null;
  private isClosed: boolean = false;
  public failOnCanary: boolean = false;
  public failOnMigration: boolean = false;
  public appliedPragmas: string[] = [];

  constructor() {
    this.initTables();
  }

  private initTables() {
    this.tables.set("app_meta", { rows: [], autoInc: 1 });
    this.tables.set("local_patients", { rows: [], autoInc: 1 });
    this.tables.set("local_glucose_observations", { rows: [], autoInc: 1 });
    this.tables.set("local_meals", { rows: [], autoInc: 1 });
    this.tables.set("local_care_tasks", { rows: [], autoInc: 1 });
    this.tables.set("local_notifications", { rows: [], autoInc: 1 });
    this.tables.set("local_documents", { rows: [], autoInc: 1 });
    this.tables.set("mutation_outbox", { rows: [], autoInc: 1 });
  }

  setEncryptionKey(key: string) {
    this.encryptionKey = key;
  }

  getEncryptionKey(): string | null {
    return this.encryptionKey;
  }

  async execAsync(sql: string): Promise<void> {
    if (this.isClosed) throw new Error("Cannot execute on closed database.");
    if (this.failOnMigration && sql.includes("CREATE TABLE")) {
      throw new Error("Disk I/O error or migration syntax failure.");
    }

    const lines = sql.split(";").map((s) => s.trim()).filter(Boolean);
    for (const line of lines) {
      if (line.startsWith("PRAGMA")) {
        this.appliedPragmas.push(line);
        if (line.includes("PRAGMA key")) {
          const match = line.match(/PRAGMA key\s*=\s*["']x'([^']+)'["']/);
          if (match && match[1]) {
            this.encryptionKey = match[1];
          }
        }
        continue;
      }

      if (line.startsWith("INSERT OR REPLACE INTO app_meta") || line.startsWith("INSERT INTO app_meta")) {
        const table = this.tables.get("app_meta")!;
        const valMatch = line.match(/'schema_version',\s*'([^']+)'/);
        const version = valMatch && valMatch[1] ? valMatch[1] : "1";
        const existingIdx = table.rows.findIndex((r) => r.key === "schema_version");
        if (existingIdx >= 0 && table.rows[existingIdx]) {
          table.rows[existingIdx]!.value = version;
        } else {
          table.rows.push({ key: "schema_version", value: version, updated_at: new Date().toISOString() });
        }
        continue;
      }

      if (line.startsWith("DELETE FROM")) {
        const tableMatch = line.match(/DELETE FROM\s+(\w+)(?:\s+WHERE\s+(.+))?/i);
        if (tableMatch && tableMatch[1]) {
          const tableName = tableMatch[1];
          const whereClause = tableMatch[2];
          const table = this.tables.get(tableName);
          if (table) {
            if (!whereClause) {
              table.rows = [];
            } else {
              const tenantMatch = whereClause.match(/tenant_id\s*=\s*'([^']+)'/);
              const userMatch = whereClause.match(/user_id\s*=\s*'([^']+)'/);
              if (tenantMatch && userMatch && tenantMatch[1] && userMatch[1]) {
                table.rows = table.rows.filter(
                  (r) => !(r.tenant_id === tenantMatch[1] && r.user_id === userMatch[1])
                );
              }
            }
          }
        }
      }

      if (line.startsWith("INSERT INTO local_documents")) {
        const table = this.tables.get("local_documents")!;
        const valsMatch = line.match(/VALUES\s*\((.+)\)/is);
        if (valsMatch && valsMatch[1]) {
          const vals = valsMatch[1].split(",").map((v) => v.trim().replace(/^['"]|['"]$/g, ""));
          table.rows.push({
            id: vals[0] ?? "",
            tenant_id: vals[1] ?? "",
            user_id: vals[2] ?? "",
            patient_id: vals[3] ?? "",
            kind: vals[4] ?? "",
            filename: vals[5] ?? "",
            file_size_bytes: parseInt(vals[6] ?? "1024", 10) || 1024,
            content_type: vals[7] ?? "",
            created_at: new Date().toISOString(),
          });
        }
        continue;
      }
    }
  }

  async runAsync(sql: string, params?: unknown[]): Promise<{ lastInsertRowId: number; changes: number }> {
    if (this.isClosed) throw new Error("Cannot run query on closed database.");
    const p = params ?? [];

    if (sql.includes("INSERT INTO local_glucose_observations")) {
      const table = this.tables.get("local_glucose_observations")!;
      const row = {
        local_id: p[0],
        server_id: p[1],
        tenant_id: p[2],
        user_id: p[3],
        patient_id: p[4],
        value_mg_dl: p[5],
        tag: p[6],
        taken_at: p[7],
        sync_status: p[8],
        idempotency_key: p[9],
        created_at: p[10],
        synced_at: p[11],
      };
      table.rows.push(row);
      return { lastInsertRowId: table.rows.length, changes: 1 };
    }

    if (sql.includes("INSERT INTO local_meals")) {
      const table = this.tables.get("local_meals")!;
      const row = {
        local_id: p[0],
        server_id: p[1],
        tenant_id: p[2],
        user_id: p[3],
        patient_id: p[4],
        description: p[5],
        portion_size: p[6],
        portion_count: p[7],
        portion_grams: p[8],
        recorded_at: p[9],
        sync_status: p[10],
        idempotency_key: p[11],
        created_at: p[12],
        synced_at: p[13],
      };
      table.rows.push(row);
      return { lastInsertRowId: table.rows.length, changes: 1 };
    }

    if (sql.includes("INSERT OR REPLACE INTO local_care_tasks")) {
      const table = this.tables.get("local_care_tasks")!;
      const row = {
        local_id: p[0],
        server_id: p[1],
        tenant_id: p[2],
        user_id: p[3],
        patient_id: p[4],
        title: p[5],
        description: p[6],
        task_type: p[7],
        status: p[8],
        priority: p[9],
        due_date: p[10],
        sync_status: p[11],
        created_at: p[12],
        updated_at: p[13],
      };
      const idx = table.rows.findIndex((r) => r.server_id === row.server_id || r.local_id === row.local_id);
      if (idx >= 0) {
        table.rows[idx] = row;
      } else {
        table.rows.push(row);
      }
      return { lastInsertRowId: table.rows.length, changes: 1 };
    }

    if (sql.includes("INSERT INTO mutation_outbox")) {
      const table = this.tables.get("mutation_outbox")!;
      const seq = table.autoInc++;
      const row = {
        id: p[0],
        seq,
        tenant_id: p[1],
        user_id: p[2],
        mutation_type: p[3],
        endpoint: p[4],
        http_method: p[5],
        payload_json: p[6],
        idempotency_key: p[7],
        local_entity_id: p[8],
        entity_type: p[9],
        attempt_count: 0,
        status: "PENDING",
        last_error_code: null,
        last_error_message: null,
        next_retry_at: null,
        created_at: p[10] ?? new Date().toISOString(),
        synced_at: null,
      };
      table.rows.push(row);
      return { lastInsertRowId: seq, changes: 1 };
    }

    if (sql.includes("UPDATE mutation_outbox")) {
      const table = this.tables.get("mutation_outbox")!;
      if (sql.includes("status = 'SYNCING'")) {
        const id = p[0];
        const row = table.rows.find((r) => r.id === id);
        if (row) row.status = "SYNCING";
        return { lastInsertRowId: 0, changes: 1 };
      }
      if (sql.includes("status = 'SYNCED'")) {
        const syncedAt = p[0];
        const id = p[1];
        const row = table.rows.find((r) => r.id === id);
        if (row) {
          row.status = "SYNCED";
          row.synced_at = syncedAt;
        }
        return { lastInsertRowId: 0, changes: 1 };
      }
      if (sql.includes("attempt_count = attempt_count + 1")) {
        const id = p[p.length - 1];
        const row = table.rows.find((r) => r.id === id);
        if (row) {
          row.attempt_count++;
          if (sql.includes("SET status = ?")) {
            row.status = p[0];
            row.last_error_code = p[1];
            row.last_error_message = p[2];
          } else {
            row.status = "PENDING";
            row.next_retry_at = p[0];
            row.last_error_code = p[1];
            row.last_error_message = p[2];
          }
        }
        return { lastInsertRowId: 0, changes: 1 };
      }
      if (sql.includes("next_retry_at = NULL")) {
        const key = p[0];
        const row = table.rows.find((r) => r.idempotency_key === key || r.id === key);
        if (row) {
          row.next_retry_at = null;
        }
        return { lastInsertRowId: 0, changes: 1 };
      }
    }

    if (sql.includes("UPDATE local_glucose_observations")) {
      const table = this.tables.get("local_glucose_observations")!;
      if (sql.includes("SET server_id = ?")) {
        const serverId = p[0];
        const syncedAt = p[1];
        const localId = p[2];
        const row = table.rows.find((r) => r.local_id === localId);
        if (row) {
          row.server_id = serverId;
          row.sync_status = "SYNCED";
          row.synced_at = syncedAt;
        }
      } else if (sql.includes("SET sync_status = ?")) {
        const status = p[0];
        const localId = p[1];
        const row = table.rows.find((r) => r.local_id === localId);
        if (row) row.sync_status = status;
      }
      return { lastInsertRowId: 0, changes: 1 };
    }

    if (sql.includes("UPDATE local_meals")) {
      const table = this.tables.get("local_meals")!;
      if (sql.includes("SET server_id = ?")) {
        const serverId = p[0];
        const syncedAt = p[1];
        const localId = p[2];
        const row = table.rows.find((r) => r.local_id === localId);
        if (row) {
          row.server_id = serverId;
          row.sync_status = "SYNCED";
          row.synced_at = syncedAt;
        }
      } else if (sql.includes("SET sync_status = ?")) {
        const status = p[0];
        const localId = p[1];
        const row = table.rows.find((r) => r.local_id === localId);
        if (row) row.sync_status = status;
      }
      return { lastInsertRowId: 0, changes: 1 };
    }

    if (sql.includes("UPDATE local_care_tasks")) {
      const table = this.tables.get("local_care_tasks")!;
      const status = p[0];
      const syncStatus = p[1];
      const updatedAt = p[2];
      const serverId = p[3];
      const row = table.rows.find((r) => r.server_id === serverId);
      if (row) {
        row.status = status;
        row.sync_status = syncStatus;
        row.updated_at = updatedAt;
      }
      return { lastInsertRowId: 0, changes: 1 };
    }

    if (sql.includes("DELETE FROM")) {
      const match = sql.match(/DELETE FROM\s+(\w+)(?:\s+WHERE\s+(.+))?/i);
      if (match && match[1]) {
        const table = this.tables.get(match[1]);
        if (table) {
          if (p.length >= 2) {
            const tenantId = p[0];
            const userId = p[1];
            table.rows = table.rows.filter(
              (r) => !(r.tenant_id === tenantId && r.user_id === userId)
            );
          } else if (!match[2]) {
            table.rows = [];
          }
        }
      }
      return { lastInsertRowId: 0, changes: 1 };
    }

    return { lastInsertRowId: 0, changes: 0 };
  }

  async getFirstAsync<T>(sql: string, params?: unknown[]): Promise<T | null> {
    if (this.failOnCanary && sql.includes("sqlite_master")) {
      throw new Error("SQLCipher: file is encrypted or is not a database");
    }
    const all = await this.getAllAsync<T>(sql, params);
    const first = all[0];
    return first !== undefined ? first : null;
  }

  async getAllAsync<T>(sql: string, params?: unknown[]): Promise<T[]> {
    if (this.isClosed) throw new Error("Cannot query closed database.");
    const p = params ?? [];

    if (sql.includes("sqlite_master")) {
      return [{ count: 8 } as unknown as T];
    }

    if (sql.includes("FROM app_meta")) {
      const table = this.tables.get("app_meta")!;
      const row = table.rows.find((r) => r.key === "schema_version");
      return row ? ([row] as unknown as T[]) : [];
    }

    if (sql.includes("FROM local_glucose_observations")) {
      const table = this.tables.get("local_glucose_observations")!;
      if (sql.includes("WHERE local_id = ?")) {
        return table.rows.filter((r) => r.local_id === p[0]) as unknown as T[];
      }
      if (sql.includes("WHERE tenant_id = ? AND user_id = ? AND patient_id = ?")) {
        return table.rows.filter(
          (r) => r.tenant_id === p[0] && r.user_id === p[1] && r.patient_id === p[2]
        ) as unknown as T[];
      }
      return table.rows as unknown as T[];
    }

    if (sql.includes("FROM local_meals")) {
      const table = this.tables.get("local_meals")!;
      if (sql.includes("WHERE tenant_id = ? AND user_id = ? AND patient_id = ?")) {
        return table.rows.filter(
          (r) => r.tenant_id === p[0] && r.user_id === p[1] && r.patient_id === p[2]
        ) as unknown as T[];
      }
      return table.rows as unknown as T[];
    }

    if (sql.includes("FROM local_documents")) {
      const table = this.tables.get("local_documents")!;
      return table.rows as unknown as T[];
    }

    if (sql.includes("FROM local_care_tasks")) {
      const table = this.tables.get("local_care_tasks")!;
      if (sql.includes("WHERE server_id = ?")) {
        return table.rows.filter((r) => r.server_id === p[0]) as unknown as T[];
      }
      if (sql.includes("WHERE tenant_id = ? AND user_id = ?")) {
        return table.rows.filter((r) => r.tenant_id === p[0] && r.user_id === p[1]) as unknown as T[];
      }
      return table.rows as unknown as T[];
    }

    if (sql.includes("FROM mutation_outbox")) {
      const table = this.tables.get("mutation_outbox")!;
      if (sql.includes("count(*) as count")) {
        const matching = table.rows.filter(
          (r) =>
            r.tenant_id === p[0] &&
            r.user_id === p[1] &&
            (r.status === "PENDING" || r.status === "SYNCING")
        );
        return [{ count: matching.length } as unknown as T];
      }
      if (sql.includes("WHERE id = ?")) {
        return table.rows.filter((r) => r.id === p[0]) as unknown as T[];
      }
      if (sql.includes("WHERE idempotency_key = ?")) {
        return table.rows.filter((r) => r.idempotency_key === p[0]) as unknown as T[];
      }
      if (sql.includes("ORDER BY seq ASC, created_at ASC")) {
        const tenantId = p[0];
        const userId = p[1];
        const nowIso = p[2] as string;
        const limit = (p[3] as number) ?? 50;

        const filtered = table.rows
          .filter(
            (r) =>
              r.tenant_id === tenantId &&
              r.user_id === userId &&
              (r.status === "PENDING" || r.status === "SYNCING") &&
              (!r.next_retry_at || r.next_retry_at <= nowIso)
          )
          .sort((a, b) => a.seq - b.seq)
          .slice(0, limit);

        return filtered as unknown as T[];
      }
      return table.rows as unknown as T[];
    }

    return [];
  }

  async withTransactionAsync<T>(task: () => Promise<T>): Promise<T> {
    // Snapshot state for atomicity rollback
    const backup = new Map<string, any[]>();
    for (const [name, store] of this.tables.entries()) {
      backup.set(name, JSON.parse(JSON.stringify(store.rows)));
    }

    try {
      return await task();
    } catch (err) {
      // Rollback
      for (const [name, rows] of backup.entries()) {
        this.tables.get(name)!.rows = rows;
      }
      throw err;
    }
  }

  async closeAsync(): Promise<void> {
    this.isClosed = true;
  }
}
