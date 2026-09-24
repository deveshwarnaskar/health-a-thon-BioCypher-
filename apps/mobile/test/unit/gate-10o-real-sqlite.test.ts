import { describe, it, expect, beforeEach, afterEach } from "vitest";
import * as fs from "node:fs";
import * as path from "node:path";
import * as os from "node:os";
import { RealEngineSqliteDatabase } from "./helpers/realEngineDatabase";
import { runLocalMigrations } from "../../src/db/migrations";
import {
  LocalDatabaseManager,
  DatabaseCorruptionError,
} from "../../src/db/database";
import {
  LocalSessionIsolationManager,
  type LocalSessionContext,
} from "../../src/db/isolation";
import { GlucoseRepository } from "../../src/db/repositories";
import { MutationOutboxRepository } from "../../src/sync/outbox";

describe("Gate 10O-R — Real Native SQLite 3 Engine Verification Suite", () => {
  let tempDbDir: string;

  beforeEach(() => {
    tempDbDir = fs.mkdtempSync(path.join(os.tmpdir(), "thali_real_sqlite_"));
  });

  afterEach(() => {
    try {
      fs.rmSync(tempDbDir, { recursive: true, force: true });
    } catch {
      // Cleanup best effort
    }
  });

  // ──────────────────────────────────────────────────────────────────────────
  // REQUIREMENT A: Fresh Database & INITIAL_MIGRATION_SQL
  // ──────────────────────────────────────────────────────────────────────────

  it("A: executes INITIAL_MIGRATION_SQL on a real native C SQLite 3 engine without syntax errors", async () => {
    const realDb = new RealEngineSqliteDatabase(":memory:");

    // Run migrations using production migration logic
    await runLocalMigrations(realDb);

    // Verify all 8 core tables exist in native SQLite sqlite_master
    const tables = await realDb.getAllAsync<{ name: string }>(
      "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
    );
    const tableNames = tables.map((t) => t.name);

    expect(tableNames).toContain("app_meta");
    expect(tableNames).toContain("local_patients");
    expect(tableNames).toContain("local_glucose_observations");
    expect(tableNames).toContain("local_meals");
    expect(tableNames).toContain("local_care_tasks");
    expect(tableNames).toContain("local_notifications");
    expect(tableNames).toContain("local_documents");
    expect(tableNames).toContain("mutation_outbox");
    expect(tableNames).toContain("sqlite_sequence");

    // Verify schema_version is recorded as 1
    const meta = await realDb.getFirstAsync<{ value: string }>(
      "SELECT value FROM app_meta WHERE key = 'schema_version';"
    );
    expect(meta?.value).toBe("1");

    await realDb.closeAsync();
  });

  // ──────────────────────────────────────────────────────────────────────────
  // REQUIREMENT B: mutation_outbox Schema & Deterministic FIFO Sequencing
  // ──────────────────────────────────────────────────────────────────────────

  it("B: confirms single primary-key AUTOINCREMENT seq and UNIQUE id on real SQLite with FIFO ordering", async () => {
    const realDb = new RealEngineSqliteDatabase(":memory:");
    await runLocalMigrations(realDb);

    const outboxRepo = new MutationOutboxRepository(realDb);
    const context: LocalSessionContext = {
      tenantId: "tenant-real-1",
      userId: "user-real-1",
      roles: ["Patient"],
    };

    // 1. Enqueue 3 mutations (seq omitted; autoincremented by native SQLite engine)
    await outboxRepo.enqueue({
      id: "out-uuid-1",
      tenantId: context.tenantId,
      userId: context.userId,
      mutationType: "INGEST_GLUCOSE",
      endpoint: "/api/v2/clinical/observations",
      httpMethod: "POST",
      payloadJson: JSON.stringify({ value_mg_dl: 120 }),
      idempotencyKey: "idem-real-1",
      localEntityId: "loc-1",
      entityType: "glucose",
      lastErrorCode: null,
      lastErrorMessage: null,
      nextRetryAt: null,
      createdAt: "2026-09-18T00:01:00Z",
    });

    await outboxRepo.enqueue({
      id: "out-uuid-2",
      tenantId: context.tenantId,
      userId: context.userId,
      mutationType: "LOG_MEAL",
      endpoint: "/api/v2/patient/meals",
      httpMethod: "POST",
      payloadJson: JSON.stringify({ description: "Dal roti" }),
      idempotencyKey: "idem-real-2",
      localEntityId: "loc-2",
      entityType: "meal",
      lastErrorCode: null,
      lastErrorMessage: null,
      nextRetryAt: null,
      createdAt: "2026-09-18T00:02:00Z",
    });

    await outboxRepo.enqueue({
      id: "out-uuid-3",
      tenantId: context.tenantId,
      userId: context.userId,
      mutationType: "START_TASK",
      endpoint: "/api/v2/clinical/care-tasks/task-99/start",
      httpMethod: "POST",
      payloadJson: "{}",
      idempotencyKey: "idem-real-3",
      localEntityId: "task-99",
      entityType: "care_task",
      lastErrorCode: null,
      lastErrorMessage: null,
      nextRetryAt: null,
      createdAt: "2026-09-18T00:03:00Z",
    });

    // 2. Fetch pending mutations: MUST be ordered strictly by seq ASC (FIFO)
    const pending = await outboxRepo.getPendingMutations(context);
    expect(pending).toHaveLength(3);
    expect(pending[0]!.id).toBe("out-uuid-1");
    expect(pending[0]!.seq).toBe(1);
    expect(pending[1]!.id).toBe("out-uuid-2");
    expect(pending[1]!.seq).toBe(2);
    expect(pending[2]!.id).toBe("out-uuid-3");
    expect(pending[2]!.seq).toBe(3);

    // 3. Confirm UNIQUE constraint on id: attempting duplicate insert throws SQLite error
    await expect(
      outboxRepo.enqueue({
        id: "out-uuid-1", // duplicate id!
        tenantId: context.tenantId,
        userId: context.userId,
        mutationType: "INGEST_GLUCOSE",
        endpoint: "/api/v2/clinical/observations",
        httpMethod: "POST",
        payloadJson: "{}",
        idempotencyKey: "idem-diff",
        localEntityId: null,
        entityType: "glucose",
        lastErrorCode: null,
        lastErrorMessage: null,
        nextRetryAt: null,
        createdAt: "2026-09-18T00:04:00Z",
      })
    ).rejects.toThrow();

    await realDb.closeAsync();
  });

  // ──────────────────────────────────────────────────────────────────────────
  // REQUIREMENT C & D: Canary Verification & Safe Failure on Corruption
  // ──────────────────────────────────────────────────────────────────────────

  it("C & D: validates canary check on real SQLite and fails closed without silent database recreation", async () => {
    const realDb = new RealEngineSqliteDatabase(":memory:");
    await runLocalMigrations(realDb);

    // Canary check on real engine
    const canary = await realDb.getFirstAsync<{ count: number }>(
      "SELECT count(*) as count FROM sqlite_master;"
    );
    expect(canary).not.toBeNull();
    expect(Number(canary?.count)).toBeGreaterThan(0);

    // Simulate corrupted database / cipher rejection
    const failingDbFactory = async () => {
      const db = new RealEngineSqliteDatabase(":memory:");
      // Close immediately so queries fail
      await db.closeAsync();
      return db;
    };

    const fakeKeyManager = {
      getOrCreateDatabaseKey: async () => "a".repeat(64),
      getDatabaseKey: async () => "a".repeat(64),
      clearDatabaseKey: async () => {},
    } as any;

    const manager = new LocalDatabaseManager();
    await expect(
      manager.open({
        databaseName: "corrupt_test.db",
        keyManager: fakeKeyManager,
        dbFactory: failingDbFactory,
      })
    ).rejects.toThrow(DatabaseCorruptionError);

    await realDb.closeAsync();
  });

  // ──────────────────────────────────────────────────────────────────────────
  // REQUIREMENT E: Persistence Across Real Database Close and Reopen
  // ──────────────────────────────────────────────────────────────────────────

  it("E: confirms data persists across real disk-backed database close and reopen", async () => {
    const dbPath = path.join(tempDbDir, "persistence_test.db");

    // Phase 1: Open, migrate, insert records
    const db1 = new RealEngineSqliteDatabase(dbPath);
    await runLocalMigrations(db1);

    const context: LocalSessionContext = {
      tenantId: "tenant-persist",
      userId: "user-persist",
      roles: ["Patient"],
    };

    const glucoseRepo1 = new GlucoseRepository(db1);
    await glucoseRepo1.insert({
      localId: "loc-glucose-p1",
      serverId: null,
      tenantId: context.tenantId,
      userId: context.userId,
      patientId: "pat-1",
      valueMgDl: 142,
      tag: "fasting",
      takenAt: "2026-09-18T06:30:00Z",
      syncStatus: "SAVED_LOCALLY",
      idempotencyKey: "idem-persist-1",
      createdAt: "2026-09-18T06:30:00Z",
      syncedAt: null,
    });

    await db1.closeAsync();

    // Phase 2: Reopen from disk with a brand-new connection instance
    const db2 = new RealEngineSqliteDatabase(dbPath);
    const glucoseRepo2 = new GlucoseRepository(db2);
    const loaded = await glucoseRepo2.findByPatient(context, "pat-1");

    expect(loaded).toHaveLength(1);
    expect(loaded[0]!.localId).toBe("loc-glucose-p1");
    expect(loaded[0]!.valueMgDl).toBe(142);
    expect(loaded[0]!.syncStatus).toBe("SAVED_LOCALLY");
    expect(loaded[0]!.idempotencyKey).toBe("idem-persist-1");

    await db2.closeAsync();
  });

  // ──────────────────────────────────────────────────────────────────────────
  // REQUIREMENT F: Outbox Durability & Byte-Identical Idempotency Key
  // ──────────────────────────────────────────────────────────────────────────

  it("F: persists pending outbox mutation and verifies byte-identical idempotency key across restarts", async () => {
    const dbPath = path.join(tempDbDir, "outbox_durability.db");

    // Session 1: Enqueue mutation
    const db1 = new RealEngineSqliteDatabase(dbPath);
    await runLocalMigrations(db1);

    const context: LocalSessionContext = {
      tenantId: "tenant-durable",
      userId: "user-durable",
      roles: ["Patient"],
    };

    const exactIdempotencyKey = "550e8400-e29b-41d4-a716-446655440000";
    const payload = JSON.stringify({
      patient_id: "pat-durable",
      value_mg_dl: 115,
      tag: "bedtime",
    });

    const outbox1 = new MutationOutboxRepository(db1);
    await outbox1.enqueue({
      id: "out-durable-1",
      tenantId: context.tenantId,
      userId: context.userId,
      mutationType: "INGEST_GLUCOSE",
      endpoint: "/api/v2/clinical/observations",
      httpMethod: "POST",
      payloadJson: payload,
      idempotencyKey: exactIdempotencyKey,
      localEntityId: "loc-durable-1",
      entityType: "glucose",
      lastErrorCode: null,
      lastErrorMessage: null,
      nextRetryAt: null,
      createdAt: "2026-09-18T07:00:00Z",
    });

    await db1.closeAsync();

    // Session 2: Fresh database instance after app crash/restart
    const db2 = new RealEngineSqliteDatabase(dbPath);
    const outbox2 = new MutationOutboxRepository(db2);
    const pending = await outbox2.getPendingMutations(context);

    expect(pending).toHaveLength(1);
    expect(pending[0]!.id).toBe("out-durable-1");
    expect(pending[0]!.idempotencyKey).toBe(exactIdempotencyKey);
    expect(pending[0]!.payloadJson).toBe(payload);
    expect(pending[0]!.status).toBe("PENDING");
    expect(pending[0]!.attemptCount).toBe(0);

    await db2.closeAsync();
  });

  // ──────────────────────────────────────────────────────────────────────────
  // FINDING-10O-02: Parameterized purgeUserData & Injection Resistance
  // ──────────────────────────────────────────────────────────────────────────

  it("10O-02: verifies parameterized purgeUserData safely handles SQL injection payloads without altering database structure", async () => {
    const realDb = new RealEngineSqliteDatabase(":memory:");
    await runLocalMigrations(realDb);

    const isolation = new LocalSessionIsolationManager();
    const glucoseRepo = new GlucoseRepository(realDb);

    // Insert legitimate record for User A
    await glucoseRepo.insert({
      localId: "g-legit",
      serverId: null,
      tenantId: "tenant-clean",
      userId: "user-clean",
      patientId: "pat-1",
      valueMgDl: 100,
      tag: null,
      takenAt: "2026-09-18T00:00:00Z",
      syncStatus: "SAVED_LOCALLY",
      idempotencyKey: "idem-legit",
      createdAt: "2026-09-18T00:00:00Z",
      syncedAt: null,
    });

    // Adversarial identifiers that would break or inject raw SQL if interpolated
    const adversarialTenants = [
      "' OR '1'='1",
      "tenant'; DROP TABLE local_patients; --",
      "'; DELETE FROM local_glucose_observations; --",
      "admin'--",
      "\\'; DROP TABLE mutation_outbox; --",
    ];

    for (const badTenant of adversarialTenants) {
      // Must execute cleanly using bound parameters without executing injection
      await isolation.purgeUserData(realDb, badTenant, "user-malicious");

      // Verify legitimate record for clean tenant was NOT purged
      const legit = await glucoseRepo.findByPatient(
        { tenantId: "tenant-clean", userId: "user-clean", roles: ["Patient"] },
        "pat-1"
      );
      expect(legit).toHaveLength(1);
      expect(legit[0]!.localId).toBe("g-legit");

      // Verify no tables were dropped by injection attempts
      const tables = await realDb.getAllAsync<{ name: string }>(
        "SELECT name FROM sqlite_master WHERE type='table';"
      );
      const names = tables.map((t) => t.name);
      expect(names).toContain("local_glucose_observations");
      expect(names).toContain("local_patients");
      expect(names).toContain("mutation_outbox");
    }

    // Now purge the legitimate user using proper bound parameters
    await isolation.purgeUserData(realDb, "tenant-clean", "user-clean");
    const remaining = await glucoseRepo.findByPatient(
      { tenantId: "tenant-clean", userId: "user-clean", roles: ["Patient"] },
      "pat-1"
    );
    expect(remaining).toHaveLength(0);

    await realDb.closeAsync();
  });

  // ──────────────────────────────────────────────────────────────────────────
  // FINDING-10O-03: Session Sign-Out Context Invalidation
  // ──────────────────────────────────────────────────────────────────────────

  it("10O-03: clears local isolation context on sign-out preventing cross-session reuse", () => {
    const isolation = new LocalSessionIsolationManager();

    // 1. User A logs in
    isolation.setContext({
      tenantId: "tenant-alice",
      userId: "user-alice",
      roles: ["Patient"],
      patientId: "patient-alice",
    });

    expect(isolation.hasContext()).toBe(true);
    const ctxA = isolation.getContext();
    expect(ctxA.userId).toBe("user-alice");

    // 2. Sign-out triggers context invalidation
    isolation.clearContext();

    expect(isolation.hasContext()).toBe(false);
    expect(() => isolation.getContext()).toThrow(
      "No active authenticated session context in local persistence."
    );

    // 3. User B logs in with clean slate
    isolation.setContext({
      tenantId: "tenant-bob",
      userId: "user-bob",
      roles: ["Caregiver"],
      patientId: null,
    });

    expect(isolation.hasContext()).toBe(true);
    const ctxB = isolation.getContext();
    expect(ctxB.userId).toBe("user-bob");
    expect(ctxB.tenantId).toBe("tenant-bob");
    expect(ctxB.roles).toEqual(["Caregiver"]);
  });
});
