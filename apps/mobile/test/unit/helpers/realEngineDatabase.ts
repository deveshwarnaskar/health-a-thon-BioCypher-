import { DatabaseSync } from "node:sqlite";
import type { IDatabaseConnection } from "../../../src/db/database";

/**
 * Real Native SQLite 3 Database Engine Adapter
 *
 * Implements IDatabaseConnection by wrapping Node.js 24's native C SQLite 3
 * DatabaseSync. This executes the actual SQLite C-parser, B-tree engine,
 * and integrity checks rather than an in-memory mock.
 */
export class RealEngineSqliteDatabase implements IDatabaseConnection {
  private db: DatabaseSync | null;
  private isClosed = false;

  constructor(filename: string = ":memory:") {
    this.db = new DatabaseSync(filename);
  }

  async execAsync(sql: string): Promise<void> {
    this.checkOpen();
    this.db!.exec(sql);
  }

  async runAsync(
    sql: string,
    params?: unknown[]
  ): Promise<{ lastInsertRowId: number; changes: number }> {
    this.checkOpen();
    const stmt = this.db!.prepare(sql);
    const result = stmt.run(...((params ?? []) as any[]));
    return {
      lastInsertRowId: Number(result.lastInsertRowid ?? 0),
      changes: Number(result.changes ?? 0),
    };
  }

  async getFirstAsync<T>(sql: string, params?: unknown[]): Promise<T | null> {
    this.checkOpen();
    const stmt = this.db!.prepare(sql);
    const row = stmt.get(...((params ?? []) as any[]));
    return (row as T) ?? null;
  }

  async getAllAsync<T>(sql: string, params?: unknown[]): Promise<T[]> {
    this.checkOpen();
    const stmt = this.db!.prepare(sql);
    const rows = stmt.all(...((params ?? []) as any[]));
    return rows as T[];
  }

  async withTransactionAsync<T>(task: () => Promise<T>): Promise<T> {
    this.checkOpen();
    this.db!.exec("BEGIN IMMEDIATE;");
    try {
      const result = await task();
      this.db!.exec("COMMIT;");
      return result;
    } catch (err) {
      this.db!.exec("ROLLBACK;");
      throw err;
    }
  }

  async closeAsync(): Promise<void> {
    if (!this.isClosed && this.db) {
      this.db.close();
      this.db = null;
      this.isClosed = true;
    }
  }

  private checkOpen(): void {
    if (this.isClosed || !this.db) {
      throw new Error("Cannot query closed real SQLite database.");
    }
  }
}
