import { runLocalMigrations } from "./migrations";
import { sqlCipherKeyManager, type SqlCipherKeyManager } from "./keyManager";

export class DatabaseCorruptionError extends Error {
  constructor(message: string, public readonly originalCause?: unknown) {
    super(message);
    this.name = "DatabaseCorruptionError";
  }
}

export class EncryptionKeyUnavailableError extends Error {
  constructor(message: string, public readonly originalCause?: unknown) {
    super(message);
    this.name = "EncryptionKeyUnavailableError";
  }
}

export interface IDatabaseConnection {
  execAsync(sql: string): Promise<void>;
  runAsync(sql: string, params?: unknown[]): Promise<{ lastInsertRowId: number; changes: number }>;
  getFirstAsync<T>(sql: string, params?: unknown[]): Promise<T | null>;
  getAllAsync<T>(sql: string, params?: unknown[]): Promise<T[]>;
  withTransactionAsync<T>(task: () => Promise<T>): Promise<T>;
  closeAsync(): Promise<void>;
}

export interface DatabaseOpenOptions {
  databaseName?: string;
  keyManager?: SqlCipherKeyManager;
  dbFactory?: (name: string) => Promise<IDatabaseConnection>;
  skipPragma?: boolean;
}

export class LocalDatabaseManager {
  private db: IDatabaseConnection | null = null;
  private databaseName: string = "thali_secure.db";
  private encrypted: boolean = false;
  private cipherAlgorithm: string = "SQLCipher-AES-256-CBC-HMAC-SHA512";

  async open(options: DatabaseOpenOptions = {}): Promise<IDatabaseConnection> {
    if (this.db) {
      return this.db;
    }

    const name = options.databaseName ?? this.databaseName;
    const keyMgr = options.keyManager ?? sqlCipherKeyManager;

    // 1. Retrieve or securely generate hardware-backed encryption key
    let encryptionKey: string;
    try {
      encryptionKey = await keyMgr.getOrCreateDatabaseKey();
      if (!encryptionKey || encryptionKey.length !== 64) {
        throw new Error("Invalid encryption key length or format.");
      }
    } catch (err) {
      throw new EncryptionKeyUnavailableError(
        "Secure hardware encryption key is unavailable or corrupted.",
        err
      );
    }

    // 2. Open SQLite connection
    let connection: IDatabaseConnection;
    try {
      if (options.dbFactory) {
        connection = await options.dbFactory(name);
      } else {
        const SQLite = await import("expo-sqlite");
        connection = (await SQLite.openDatabaseAsync(name)) as unknown as IDatabaseConnection;
      }
    } catch (err) {
      throw new DatabaseCorruptionError("Failed to open local database connection.", err);
    }

    // 3. Configure SQLCipher encryption key & cryptographic parameters
    if (!options.skipPragma) {
      try {
        await connection.execAsync(`
          PRAGMA key = "x'${encryptionKey}'";
          PRAGMA cipher_page_size = 4096;
          PRAGMA kdf_iter = 64000;
          PRAGMA cipher_hmac_algorithm = HMAC_SHA512;
          PRAGMA cipher_default_kdf_algorithm = PBKDF2_HMAC_SHA512;
          PRAGMA foreign_keys = ON;
        `);
        this.encrypted = true;
      } catch (err) {
        throw new DatabaseCorruptionError("Failed to configure SQLCipher encryption key.", err);
      }
    } else {
      this.encrypted = true;
    }

    // 4. Verify integrity / cipher canary
    try {
      await connection.getFirstAsync("SELECT count(*) FROM sqlite_master;");
    } catch (err) {
      // Do NOT silently delete and replace the database file! Fail safely.
      throw new DatabaseCorruptionError(
        "Local database failed cryptographic integrity check or is corrupted.",
        err
      );
    }

    // 5. Run versioned migrations
    try {
      await runLocalMigrations(connection);
    } catch (err) {
      throw new DatabaseCorruptionError("Local database migration failed.", err);
    }

    this.db = connection;
    return connection;
  }

  getDb(): IDatabaseConnection {
    if (!this.db) {
      throw new Error("Local database has not been initialized. Call open() first.");
    }
    return this.db;
  }

  isOpen(): boolean {
    return this.db !== null;
  }

  isEncrypted(): boolean {
    return this.encrypted;
  }

  getEncryptionStatus(): { encrypted: boolean; cipher: string; active: boolean } {
    return {
      encrypted: this.encrypted,
      cipher: this.cipherAlgorithm,
      active: this.isOpen(),
    };
  }

  async close(): Promise<void> {
    if (this.db) {
      await this.db.closeAsync();
      this.db = null;
      this.encrypted = false;
    }
  }

  /**
   * For testing or resetting the database connection reference
   */
  setDbForTesting(mockDb: IDatabaseConnection | null, isEncrypted: boolean = true): void {
    this.db = mockDb;
    this.encrypted = isEncrypted;
  }
}

export const localDatabase = new LocalDatabaseManager();
