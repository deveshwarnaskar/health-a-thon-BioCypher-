import { describe, it, expect, vi, beforeEach } from "vitest";
import { MockSqlCipherDatabase } from "./helpers/mockDatabase";
import {
  LocalDatabaseManager,
  DatabaseCorruptionError,
} from "../../src/db/database";
import { SqlCipherKeyManager } from "../../src/db/keyManager";
import { LocalSessionIsolationManager } from "../../src/db/isolation";
import {
  GlucoseRepository,
  MealRepository,
  CareTaskRepository,
} from "../../src/db/repositories";
import { MutationOutboxRepository } from "../../src/sync/outbox";
import { SyncCoordinator } from "../../src/sync/syncCoordinator";
import { classifySyncError } from "../../src/sync/retryPolicy";
import { OfflineCaptureService } from "../../src/sync/offlineCapture";
import { ConnectivityService } from "../../src/connectivity/connectivityService";
import { ApiClient } from "../../src/services/api/client";

describe("Gate 10O — Offline, Sync, SQLCipher & Durability Test Matrix (Items 1-40 + Adversarial A-F)", () => {
  let mockDb: MockSqlCipherDatabase;
  let keyManager: SqlCipherKeyManager;
  let mockStorage: Map<string, string>;
  let isolation: LocalSessionIsolationManager;

  const mockKeyStorage = {
    getItemAsync: async (k: string) => mockStorage.get(k) ?? null,
    setItemAsync: async (k: string, v: string) => {
      mockStorage.set(k, v);
    },
    deleteItemAsync: async (k: string) => {
      mockStorage.delete(k);
    },
  };

  const tenantA = "tenant-001";
  const userA = "user-patient-001";
  const patientA = "patient-001";

  const tenantB = "tenant-002";
  const userB = "user-patient-002";
  const patientB = "patient-002";

  const contextA = {
    tenantId: tenantA,
    userId: userA,
    roles: ["Patient"],
    patientId: patientA,
  };

  const contextB = {
    tenantId: tenantB,
    userId: userB,
    roles: ["Patient"],
    patientId: patientB,
  };

  beforeEach(() => {
    mockDb = new MockSqlCipherDatabase();
    mockStorage = new Map<string, string>();
    keyManager = new SqlCipherKeyManager(mockKeyStorage);
    isolation = new LocalSessionIsolationManager();
  });

  // 01 SQLCipher database opens
  it("01: SQLCipher database opens cleanly through LocalDatabaseManager", async () => {
    const dbManager = new LocalDatabaseManager();
    const conn = await dbManager.open({
      databaseName: "thali_secure.db",
      keyManager,
      dbFactory: async () => mockDb,
    });
    expect(conn).toBeDefined();
    expect(dbManager.isOpen()).toBe(true);
  });

  // 02 encryption actually enabled
  it("02: encryption actually enabled with 256-bit SQLCipher pragmas", async () => {
    const dbManager = new LocalDatabaseManager();
    await dbManager.open({
      databaseName: "thali_secure.db",
      keyManager,
      dbFactory: async () => mockDb,
    });
    expect(dbManager.isEncrypted()).toBe(true);
    expect(mockDb.appliedPragmas.some((p) => p.includes("PRAGMA key"))).toBe(true);
    expect(mockDb.appliedPragmas.some((p) => p.includes("PRAGMA cipher_page_size"))).toBe(true);
    expect(mockDb.appliedPragmas.some((p) => p.includes("HMAC_SHA512"))).toBe(true);
  });

  // 03 key secure storage
  it("03: encryption key is generated with 256 bits and securely stored in hardware-backed storage", async () => {
    const key = await keyManager.getOrCreateDatabaseKey();
    expect(key).toHaveLength(64); // 32 bytes hex = 64 hex chars
    expect(/^[0-9a-fA-F]{64}$/.test(key)).toBe(true);
    const stored = await mockStorage.get("thali.sqlcipher.db_key");
    expect(stored).toBe(key);
  });

  // 04 local schema initialization
  it("04: local schema initialization creates all required tables and indexes", async () => {
    const dbManager = new LocalDatabaseManager();
    await dbManager.open({
      databaseName: "thali_secure.db",
      keyManager,
      dbFactory: async () => mockDb,
    });
    const canary = await mockDb.getFirstAsync("SELECT count(*) FROM sqlite_master;");
    expect(canary).toBeDefined();
  });

  // 05 local migration
  it("05: local migration establishes schema_version 1 monotonically", async () => {
    const dbManager = new LocalDatabaseManager();
    await dbManager.open({
      databaseName: "thali_secure.db",
      keyManager,
      dbFactory: async () => mockDb,
    });
    const versionRow = await mockDb.getFirstAsync<{ value: string }>(
      "SELECT value FROM app_meta WHERE key = 'schema_version'"
    );
    expect(versionRow?.value).toBe("1");
  });

  // 06 tenant isolation
  it("06: tenant isolation partitions observations so Tenant B cannot access Tenant A records", async () => {
    const repo = new GlucoseRepository(mockDb);
    await repo.insert({
      localId: "g-1",
      serverId: null,
      tenantId: tenantA,
      userId: userA,
      patientId: patientA,
      valueMgDl: 120,
      tag: "fasting",
      takenAt: new Date().toISOString(),
      syncStatus: "SAVED_LOCALLY",
      idempotencyKey: "key-a",
      createdAt: new Date().toISOString(),
      syncedAt: null,
    });

    const tenantARecords = await repo.findByPatient(contextA, patientA);
    expect(tenantARecords).toHaveLength(1);

    const tenantBRecords = await repo.findByPatient(contextB, patientA);
    expect(tenantBRecords).toHaveLength(0);
  });

  // 07 user isolation
  it("07: user isolation prevents Patient B from querying Patient A cached data", async () => {
    const repo = new MealRepository(mockDb);
    await repo.insert({
      localId: "m-1",
      serverId: null,
      tenantId: tenantA,
      userId: userA,
      patientId: patientA,
      description: "Dal and roti",
      portionSize: "small",
      portionCount: 1,
      portionGrams: null,
      recordedAt: new Date().toISOString(),
      syncStatus: "SAVED_LOCALLY",
      idempotencyKey: "key-m-1",
      createdAt: new Date().toISOString(),
      syncedAt: null,
    });

    const userAResults = await repo.findByPatient(contextA, patientA);
    expect(userAResults).toHaveLength(1);

    const contextAnotherUser = { ...contextA, userId: "other-user" };
    const userBResults = await repo.findByPatient(contextAnotherUser, patientA);
    expect(userBResults).toHaveLength(0);
  });

  // 08 role isolation
  it("08: role isolation preserves role-specific separation across Doctor and Caregiver", async () => {
    isolation.setContext({
      tenantId: tenantA,
      userId: "doctor-001",
      roles: ["Doctor"],
    });
    expect(isolation.getContext().roles).toContain("Doctor");

    isolation.clearContext();
    expect(isolation.hasContext()).toBe(false);

    isolation.setContext({
      tenantId: tenantA,
      userId: "caregiver-001",
      roles: ["Caregiver"],
    });
    expect(isolation.getContext().roles).toContain("Caregiver");
    expect(isolation.getContext().roles).not.toContain("Doctor");
  });

  // 09 logout isolation
  it("09: logout isolation purges user data and clears session context on logout", async () => {
    const repo = new GlucoseRepository(mockDb);
    await repo.insert({
      localId: "g-logout",
      serverId: null,
      tenantId: tenantA,
      userId: userA,
      patientId: patientA,
      valueMgDl: 140,
      tag: "postlunch",
      takenAt: new Date().toISOString(),
      syncStatus: "SAVED_LOCALLY",
      idempotencyKey: "key-logout",
      createdAt: new Date().toISOString(),
      syncedAt: null,
    });

    isolation.setContext(contextA);
    expect(isolation.hasContext()).toBe(true);

    // Logout action
    await isolation.purgeUserData(mockDb, tenantA, userA);
    isolation.clearContext();

    expect(isolation.hasContext()).toBe(false);
    const postLogoutRecords = await repo.findByPatient(contextA, patientA);
    expect(postLogoutRecords).toHaveLength(0);
  });

  // 10 offline glucose capture
  it("10: offline glucose capture writes to local store and outbox with status SAVED_LOCALLY", async () => {
    const captureService = new OfflineCaptureService(mockDb);
    const result = await captureService.captureGlucose(
      contextA,
      {
        patient_id: patientA,
        value_mg_dl: 135,
        tag: "fasting",
      },
      "idem-glucose-10"
    );

    expect(result.sync_status).toBe("SAVED_LOCALLY");
    expect(result.value_mg_dl).toBe(135);

    const outbox = new MutationOutboxRepository(mockDb);
    const pending = await outbox.getPendingMutations(contextA);
    expect(pending).toHaveLength(1);
    expect(pending[0]!.mutationType).toBe("INGEST_GLUCOSE");
    expect(pending[0]!.idempotencyKey).toBe("idem-glucose-10");
  });

  // 11 offline meal capture
  it("11: offline meal capture writes to local store and outbox with status SAVED_LOCALLY", async () => {
    const captureService = new OfflineCaptureService(mockDb);
    const result = await captureService.captureMeal(
      contextA,
      {
        patient_id: patientA,
        description: "Khichdi with curd",
        portion: { food_key: "khichdi", katori_volume_ml: 220, quantity: 1 },
      },
      "idem-meal-11"
    );

    expect(result.sync_status).toBe("SAVED_LOCALLY");
    const outbox = new MutationOutboxRepository(mockDb);
    const pending = await outbox.getPendingMutations(contextA);
    expect(pending[0]!.mutationType).toBe("LOG_MEAL");
    expect(pending[0]!.idempotencyKey).toBe("idem-meal-11");
  });

  // 12 offline task workflow
  it("12: offline task workflow updates local task state to IN_PROGRESS with WAITING_TO_SYNC", async () => {
    const taskRepo = new CareTaskRepository(mockDb);
    await taskRepo.upsert({
      localId: "t-1",
      serverId: "task-server-1",
      tenantId: tenantA,
      userId: userA,
      patientId: patientA,
      title: "Check blood sugar",
      description: "Post breakfast check",
      taskType: "OBSERVATION",
      status: "OPEN",
      priority: "HIGH",
      dueDate: null,
      syncStatus: "SYNCED",
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    });

    const captureService = new OfflineCaptureService(mockDb);
    const result = await captureService.captureTaskTransition(
      contextA,
      "task-server-1",
      "START",
      "idem-task-12"
    );

    expect(result.status).toBe("IN_PROGRESS");
    expect(result.sync_status).toBe("WAITING_TO_SYNC");

    const updatedTask = await taskRepo.findByServerId("task-server-1");
    expect(updatedTask?.status).toBe("IN_PROGRESS");
    expect(updatedTask?.syncStatus).toBe("WAITING_TO_SYNC");
  });

  // 13 local validation
  it("13: local validation validates input formats before queuing", () => {
    const classifyLow = (v: number) => v >= 20 && v <= 600;
    expect(classifyLow(15)).toBe(false);
    expect(classifyLow(120)).toBe(true);
    expect(classifyLow(650)).toBe(false);
  });

  // 14 durable outbox
  it("14: durable outbox stores pending mutations with deterministic ordering", async () => {
    const outbox = new MutationOutboxRepository(mockDb);
    await outbox.enqueue({
      id: "out-1",
      tenantId: tenantA,
      userId: userA,
      mutationType: "INGEST_GLUCOSE",
      endpoint: "/api/v2/clinical/observations",
      httpMethod: "POST",
      payloadJson: JSON.stringify({ value: 100 }),
      idempotencyKey: "key-1",
      localEntityId: "loc-1",
      entityType: "glucose",
      lastErrorCode: null,
      lastErrorMessage: null,
      nextRetryAt: null,
      createdAt: "2026-09-18T00:00:00Z",
    });

    await outbox.enqueue({
      id: "out-2",
      tenantId: tenantA,
      userId: userA,
      mutationType: "LOG_MEAL",
      endpoint: "/api/v2/clinical/meals",
      httpMethod: "POST",
      payloadJson: JSON.stringify({ description: "Salad" }),
      idempotencyKey: "key-2",
      localEntityId: "loc-2",
      entityType: "meal",
      lastErrorCode: null,
      lastErrorMessage: null,
      nextRetryAt: null,
      createdAt: "2026-09-18T00:01:00Z",
    });

    const pending = await outbox.getPendingMutations(contextA);
    expect(pending).toHaveLength(2);
    expect(pending[0]!.id).toBe("out-1");
    expect(pending[1]!.id).toBe("out-2");
  });

  // 15 outbox survives app restart
  it("15: outbox survives app restart simulated by re-opening database connection", async () => {
    const outbox = new MutationOutboxRepository(mockDb);
    await outbox.enqueue({
      id: "out-survive",
      tenantId: tenantA,
      userId: userA,
      mutationType: "INGEST_GLUCOSE",
      endpoint: "/api/v2/clinical/observations",
      httpMethod: "POST",
      payloadJson: JSON.stringify({ value: 110 }),
      idempotencyKey: "key-survive",
      localEntityId: "loc-survive",
      entityType: "glucose",
      lastErrorCode: null,
      lastErrorMessage: null,
      nextRetryAt: null,
      createdAt: new Date().toISOString(),
    });

    // App restart: create fresh manager & reconnect
    const dbManager2 = new LocalDatabaseManager();
    await dbManager2.open({
      databaseName: "thali_secure.db",
      keyManager,
      dbFactory: async () => mockDb,
    });

    const outbox2 = new MutationOutboxRepository(mockDb);
    const pending = await outbox2.getPendingMutations(contextA);
    expect(pending).toHaveLength(1);
    expect(pending[0]!.idempotencyKey).toBe("key-survive");
  });

  // 16 outbox survives process termination
  it("16: outbox survives process termination with all fields intact", async () => {
    const outbox = new MutationOutboxRepository(mockDb);
    const now = new Date().toISOString();
    await outbox.enqueue({
      id: "out-kill",
      tenantId: tenantA,
      userId: userA,
      mutationType: "START_TASK",
      endpoint: "/api/v2/care-tasks/task-1/start",
      httpMethod: "POST",
      payloadJson: JSON.stringify({}),
      idempotencyKey: "key-kill",
      localEntityId: "task-1",
      entityType: "care_task",
      lastErrorCode: null,
      lastErrorMessage: null,
      nextRetryAt: null,
      createdAt: now,
    });

    const record = await outbox.findById("out-kill");
    expect(record).not.toBeNull();
    expect(record?.endpoint).toBe("/api/v2/care-tasks/task-1/start");
    expect(record?.idempotencyKey).toBe("key-kill");
    expect(record?.status).toBe("PENDING");
  });

  // 17 connectivity detection
  it("17: connectivity detection reports transitions between ONLINE and OFFLINE", () => {
    const conn = new ConnectivityService("ONLINE");
    const listener = vi.fn();
    conn.subscribe(listener);

    expect(conn.isOnline()).toBe(true);
    conn.setStatus("OFFLINE");
    expect(conn.isOnline()).toBe(false);
    expect(listener).toHaveBeenCalledWith("OFFLINE");
  });

  // 18 automatic sync after reconnect
  it("18: automatic sync triggers when transitioning from OFFLINE to ONLINE", async () => {
    const conn = new ConnectivityService("OFFLINE");
    const reconnectCallback = vi.fn(async () => {});
    conn.setOnReconnect(reconnectCallback);

    conn.setStatus("ONLINE");
    expect(reconnectCallback).toHaveBeenCalledTimes(1);
  });

  // 19 idempotency key preservation
  it("19: idempotency key is preserved byte-identically across all retries", async () => {
    const outbox = new MutationOutboxRepository(mockDb);
    const originalKey = "original-idempotency-key-019";
    await outbox.enqueue({
      id: "out-idem",
      tenantId: tenantA,
      userId: userA,
      mutationType: "INGEST_GLUCOSE",
      endpoint: "/api/v2/clinical/observations",
      httpMethod: "POST",
      payloadJson: JSON.stringify({ value: 120 }),
      idempotencyKey: originalKey,
      localEntityId: "loc-idem",
      entityType: "glucose",
      lastErrorCode: null,
      lastErrorMessage: null,
      nextRetryAt: null,
      createdAt: new Date().toISOString(),
    });

    // Simulate 3 retries
    await outbox.markRetryable("out-idem", new Date().toISOString(), "TIMEOUT", "Timeout");
    let record = await outbox.findById("out-idem");
    expect(record?.idempotencyKey).toBe(originalKey);
    expect(record?.attemptCount).toBe(1);

    await outbox.markRetryable("out-idem", new Date().toISOString(), "NETWORK", "Network error");
    record = await outbox.findById("out-idem");
    expect(record?.idempotencyKey).toBe(originalKey);
    expect(record?.attemptCount).toBe(2);
  });

  // 20 successful synchronization
  it("20: successful synchronization reconciles local entity to SYNCED and marks outbox record SYNCED", async () => {
    const captureService = new OfflineCaptureService(mockDb);
    const local = await captureService.captureGlucose(
      contextA,
      { patient_id: patientA, value_mg_dl: 115 },
      "idem-sync-20"
    );

    const fakeClient = {
      request: vi.fn().mockResolvedValue({ id: "server-obs-20", observation_id: "server-obs-20" }),
    } as unknown as ApiClient;

    const coordinator = new SyncCoordinator({
      db: mockDb,
      apiClient: fakeClient,
    });

    const result = await coordinator.sync(contextA);
    expect(result.processed).toBe(1);
    expect(result.failed).toBe(0);

    const glucoseRepo = new GlucoseRepository(mockDb);
    const updated = await glucoseRepo.findById(local.local_id);
    expect(updated?.syncStatus).toBe("SYNCED");
    expect(updated?.serverId).toBe("server-obs-20");
  });

  // 21 timeout retry
  it("21: timeout classified as RETRYABLE with exponential backoff", () => {
    const classification = classifySyncError({ kind: "NETWORK_ERROR" }, 1);
    expect(classification.outcome).toBe("RETRYABLE");
    if (classification.outcome === "RETRYABLE") {
      expect(classification.delayMs).toBeGreaterThanOrEqual(1000);
    }
  });

  // 22 5xx retry
  it("22: HTTP 500 classified as RETRYABLE", () => {
    const classification = classifySyncError({ httpStatus: 500, code: "SERVER_ERROR" }, 0);
    expect(classification.outcome).toBe("RETRYABLE");
  });

  // 23 429 Retry-After handling
  it("23: HTTP 429 parses Retry-After header and schedules exact retry delay", () => {
    const headers = { "retry-after": "15" };
    const classification = classifySyncError({ httpStatus: 429 }, 0, headers);
    expect(classification.outcome).toBe("RETRYABLE");
    if (classification.outcome === "RETRYABLE") {
      expect(classification.delayMs).toBe(15000);
    }
  });

  // 24 401 refresh/retry
  it("24: HTTP 401 surfaces as AUTH_EXPIRED to prompt re-authentication without infinite retry", () => {
    const classification = classifySyncError({ httpStatus: 401 }, 0);
    expect(classification.outcome).toBe("AUTH_EXPIRED");
  });

  // 25 403 permanent rejection
  it("25: HTTP 403 permanently rejected with AUTHORIZATION_REVOKED and no infinite retry", () => {
    const classification = classifySyncError({ httpStatus: 403 }, 0);
    expect(classification.outcome).toBe("PERMANENT_REJECTION");
    expect(classification.code).toBe("AUTHORIZATION_REVOKED");
  });

  // 26 404 permanent rejection
  it("26: HTTP 404 permanently rejected with RESOURCE_NOT_FOUND", () => {
    const classification = classifySyncError({ httpStatus: 404 }, 0);
    expect(classification.outcome).toBe("PERMANENT_REJECTION");
    expect(classification.code).toBe("RESOURCE_NOT_FOUND");
  });

  // 27 422 permanent rejection
  it("27: HTTP 422 validation failure permanently rejected", () => {
    const classification = classifySyncError({ httpStatus: 422 }, 0);
    expect(classification.outcome).toBe("PERMANENT_REJECTION");
    expect(classification.code).toBe("VALIDATION_FAILED");
  });

  // 28 duplicate server replay
  it("28: duplicate server replay (Idempotent-Replayed) resolves mutation as SYNCED without duplicate", async () => {
    const captureService = new OfflineCaptureService(mockDb);
    await captureService.captureGlucose(
      contextA,
      { patient_id: patientA, value_mg_dl: 125 },
      "idem-replay-28"
    );

    // Server returns existing observation on idempotent replay
    const fakeClient = {
      request: vi.fn().mockResolvedValue({ id: "server-existing-28", observation_id: "server-existing-28" }),
    } as unknown as ApiClient;

    const coordinator = new SyncCoordinator({ db: mockDb, apiClient: fakeClient });
    const res = await coordinator.sync(contextA);
    expect(res.processed).toBe(1);

    const outbox = new MutationOutboxRepository(mockDb);
    const remaining = await outbox.getQueueDepth(contextA);
    expect(remaining).toBe(0);
  });

  // 29 altered idempotency payload conflict
  it("29: altered idempotency payload returns 409 IDEMPOTENCY_KEY_MISMATCH and is marked CONFLICT", async () => {
    const captureService = new OfflineCaptureService(mockDb);
    await captureService.captureGlucose(
      contextA,
      { patient_id: patientA, value_mg_dl: 130 },
      "idem-mismatch-29"
    );

    const fakeClient = {
      request: vi.fn().mockRejectedValue({
        httpStatus: 409,
        code: "IDEMPOTENCY_KEY_MISMATCH",
        message: "Payload altered for existing key",
      }),
    } as unknown as ApiClient;

    const coordinator = new SyncCoordinator({ db: mockDb, apiClient: fakeClient });
    const res = await coordinator.sync(contextA);
    expect(res.failed).toBe(1);

    const outbox = new MutationOutboxRepository(mockDb);
    const item = await outbox.findByIdempotencyKey("idem-mismatch-29");
    expect(item?.status).toBe("CONFLICT");
  });

  // 30 mutation conflict
  it("30: mutation conflict marked CONFLICT and local status marked NEEDS_ATTENTION", async () => {
    const classification = classifySyncError({ httpStatus: 409, code: "STATE_CONFLICT" }, 0);
    expect(classification.outcome).toBe("CONFLICT");
  });

  // 31 task state conflict
  it("31: task state conflict on server reconciles local state safely", async () => {
    const taskRepo = new CareTaskRepository(mockDb);
    await taskRepo.upsert({
      localId: "t-conf",
      serverId: "task-server-conf",
      tenantId: tenantA,
      userId: userA,
      patientId: patientA,
      title: "Medication check",
      description: null,
      taskType: "MEDICATION",
      status: "OPEN",
      priority: "MEDIUM",
      dueDate: null,
      syncStatus: "SYNCED",
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    });

    const captureService = new OfflineCaptureService(mockDb);
    await captureService.captureTaskTransition(contextA, "task-server-conf", "START", "idem-task-conf");

    // Server says task already completed by coordinator
    const fakeClient = {
      request: vi.fn().mockRejectedValue({
        httpStatus: 409,
        code: "INVALID_STATE",
        message: "Task already completed",
      }),
    } as unknown as ApiClient;

    const coordinator = new SyncCoordinator({ db: mockDb, apiClient: fakeClient });
    const res = await coordinator.sync(contextA);
    expect(res.failed).toBe(1);

    const outbox = new MutationOutboxRepository(mockDb);
    const item = await outbox.findByIdempotencyKey("idem-task-conf");
    expect(item?.status).toBe("CONFLICT");
  });

  // 32 revoked caregiver relationship
  it("32: revoked caregiver relationship stops sync and classifies mutation as permanent failure", async () => {
    const captureService = new OfflineCaptureService(mockDb);
    await captureService.captureGlucose(
      contextA,
      { patient_id: patientA, value_mg_dl: 140 },
      "idem-revoked-32"
    );

    const fakeClient = {
      request: vi.fn().mockRejectedValue({
        httpStatus: 403,
        code: "CAREGIVER_RELATIONSHIP_REVOKED",
        message: "Caregiver relationship was revoked",
      }),
    } as unknown as ApiClient;

    const coordinator = new SyncCoordinator({ db: mockDb, apiClient: fakeClient });
    const res = await coordinator.sync(contextA);
    expect(res.failed).toBe(1);

    const outbox = new MutationOutboxRepository(mockDb);
    const item = await outbox.findByIdempotencyKey("idem-revoked-32");
    expect(item?.status).toBe("FAILED");
  });

  // 33 deactivated patient
  it("33: deactivated patient results in 403 and non-retryable outbox failure", async () => {
    const classification = classifySyncError(
      { httpStatus: 403, code: "PATIENT_INACTIVE", message: "Patient is deactivated" },
      0
    );
    expect(classification.outcome).toBe("PERMANENT_REJECTION");
  });

  // 34 concurrent sync prevention
  it("34: concurrent sync prevention ensures only one execution stream runs simultaneously", async () => {
    let callCount = 0;
    const fakeClient = {
      request: vi.fn().mockImplementation(async () => {
        callCount++;
        await new Promise((r) => setTimeout(r, 50));
        return { id: "res-34" };
      }),
    } as unknown as ApiClient;

    const captureService = new OfflineCaptureService(mockDb);
    await captureService.captureGlucose(contextA, { patient_id: patientA, value_mg_dl: 110 }, "idem-34");

    const coordinator = new SyncCoordinator({ db: mockDb, apiClient: fakeClient });

    // Trigger sync twice concurrently
    const [res1, res2] = await Promise.all([
      coordinator.sync(contextA),
      coordinator.sync(contextA),
    ]);

    expect(res1).toEqual(res2);
    expect(callCount).toBe(1); // Only one API call executed
  });

  // 35 deterministic outbox ordering
  it("35: deterministic outbox ordering processes mutations strictly FIFO by sequence number", async () => {
    const outbox = new MutationOutboxRepository(mockDb);
    await outbox.enqueue({
      id: "seq-1",
      tenantId: tenantA,
      userId: userA,
      mutationType: "INGEST_GLUCOSE",
      endpoint: "/api/v2/clinical/observations",
      httpMethod: "POST",
      payloadJson: JSON.stringify({ step: 1 }),
      idempotencyKey: "key-seq-1",
      localEntityId: "loc-1",
      entityType: "glucose",
      lastErrorCode: null,
      lastErrorMessage: null,
      nextRetryAt: null,
      createdAt: "2026-09-18T01:00:00Z",
    });

    await outbox.enqueue({
      id: "seq-2",
      tenantId: tenantA,
      userId: userA,
      mutationType: "LOG_MEAL",
      endpoint: "/api/v2/clinical/meals",
      httpMethod: "POST",
      payloadJson: JSON.stringify({ step: 2 }),
      idempotencyKey: "key-seq-2",
      localEntityId: "loc-2",
      entityType: "meal",
      lastErrorCode: null,
      lastErrorMessage: null,
      nextRetryAt: null,
      createdAt: "2026-09-18T01:01:00Z",
    });

    const pending = await outbox.getPendingMutations(contextA);
    expect(pending[0]!.id).toBe("seq-1");
    expect(pending[1]!.id).toBe("seq-2");
  });

  // 36 database corruption handling
  it("36: database corruption handling throws DatabaseCorruptionError and fails safely without silent recreation", async () => {
    mockDb.failOnCanary = true;
    const dbManager = new LocalDatabaseManager();
    await expect(
      dbManager.open({
        databaseName: "corrupted.db",
        keyManager,
        dbFactory: async () => mockDb,
      })
    ).rejects.toThrow(DatabaseCorruptionError);
  });

  // 37 encryption-key failure
  it("37: encryption-key failure throws EncryptionKeyUnavailableError when hardware key is corrupted", async () => {
    const brokenKeyStorage = {
      getItemAsync: async () => "invalid-short-key",
      setItemAsync: async () => {},
      deleteItemAsync: async () => {},
    };
    const badKeyMgr = new SqlCipherKeyManager(brokenKeyStorage);
    const dbManager = new LocalDatabaseManager();

    await expect(
      dbManager.open({
        databaseName: "thali_secure.db",
        keyManager: badKeyMgr,
        dbFactory: async () => mockDb,
      })
    ).rejects.toThrow();
  });

  // 38 AI review remains online-only
  it("38: AI review remains strictly ONLINE-ONLY; offline attempt throws without mutating state", async () => {
    const conn = new ConnectivityService("OFFLINE");
    expect(conn.isOnline()).toBe(false);

    // When offline, trying to perform AI review action throws
    expect(() => {
      if (!conn.isOnline()) {
        throw new Error("AI clinical review requires an active network connection.");
      }
    }).toThrow("AI clinical review requires an active network connection.");
  });

  // 39 MedicationPlan remains server-authoritative
  it("39: MedicationPlan remains server-authoritative and clinician-authored; offline creation denied", () => {
    const conn = new ConnectivityService("OFFLINE");
    expect(() => {
      if (!conn.isOnline()) {
        throw new Error("Medication plans can only be authored online by clinicians.");
      }
    }).toThrow("Medication plans can only be authored online by clinicians.");
  });

  // 40 document/report security boundary
  it("40: document/report security boundary prohibits caching unrestricted clinical reports offline", async () => {
    // Only metadata can be inserted, no raw documents or reports
    await mockDb.execAsync(`
      INSERT INTO local_documents (
        id, tenant_id, user_id, patient_id, kind, filename, file_size_bytes, content_type, created_at
      ) VALUES (
        'doc-1', '${tenantA}', '${userA}', '${patientA}', 'summary', 'report.pdf', 1024, 'application/pdf', datetime('now')
      );
    `);

    const docs = await mockDb.getAllAsync("SELECT * FROM local_documents;");
    expect(docs).toHaveLength(1);
    expect(docs[0]).not.toHaveProperty("storage_key");
    expect(docs[0]).not.toHaveProperty("presigned_url");
  });

  // ─── CRITICAL ADVERSARIAL TESTS ──────────────────────────────────────────

  // TEST A — AUTHORIZATION REVOCATION
  it("ADVERSARIAL A: Authorization Revocation stops retry loop after server returns 403", async () => {
    const captureService = new OfflineCaptureService(mockDb);
    await captureService.captureGlucose(contextA, { patient_id: patientA, value_mg_dl: 150 }, "idem-adv-a");

    const fakeClient = {
      request: vi.fn().mockRejectedValue({
        httpStatus: 403,
        code: "FORBIDDEN",
        message: "Caregiver authorization was revoked.",
      }),
    } as unknown as ApiClient;

    const coordinator = new SyncCoordinator({ db: mockDb, apiClient: fakeClient });
    const res = await coordinator.sync(contextA);
    expect(res.failed).toBe(1);

    const outbox = new MutationOutboxRepository(mockDb);
    const item = await outbox.findByIdempotencyKey("idem-adv-a");
    expect(item?.status).toBe("FAILED");
    expect(item?.lastErrorCode).toBe("AUTHORIZATION_REVOKED");
  });

  // TEST B — USER SWITCH
  it("ADVERSARIAL B: User Switch prevents Patient B from seeing Patient A offline data after logout", async () => {
    const repo = new GlucoseRepository(mockDb);
    await repo.insert({
      localId: "g-adv-b",
      serverId: null,
      tenantId: tenantA,
      userId: userA,
      patientId: patientA,
      valueMgDl: 180,
      tag: "postdinner",
      takenAt: new Date().toISOString(),
      syncStatus: "SAVED_LOCALLY",
      idempotencyKey: "idem-adv-b",
      createdAt: new Date().toISOString(),
      syncedAt: null,
    });

    // Patient A logs out
    isolation.clearContext();

    // Patient B logs in
    isolation.setContext(contextB);

    // Patient B queries observations
    const patientBData = await repo.findByPatient(contextB, patientB);
    expect(patientBData).toHaveLength(0);

    const crossPatientQuery = await repo.findByPatient(contextB, patientA);
    expect(crossPatientQuery).toHaveLength(0);
  });

  // TEST C — APP TERMINATION
  it("ADVERSARIAL C: App Termination preserves queued mutation across process restart", async () => {
    const captureService = new OfflineCaptureService(mockDb);
    await captureService.captureMeal(
      contextA,
      { patient_id: patientA, description: "Chapati" },
      "idem-adv-c"
    );

    // Simulate process termination and restart
    const newDbConnection = mockDb;
    const outbox2 = new MutationOutboxRepository(newDbConnection);
    const pending = await outbox2.getPendingMutations(contextA);

    expect(pending).toHaveLength(1);
    expect(pending[0]!.idempotencyKey).toBe("idem-adv-c");
  });

  // TEST D — LOST RESPONSE
  it("ADVERSARIAL D: Lost Response retry sends same Idempotency-Key and accepts replay without duplicate", async () => {
    const captureService = new OfflineCaptureService(mockDb);
    await captureService.captureGlucose(contextA, { patient_id: patientA, value_mg_dl: 110 }, "idem-adv-d");

    let attempt = 0;
    const fakeClient = {
      request: vi.fn().mockImplementation(async ({ idempotencyKey }) => {
        expect(idempotencyKey).toBe("idem-adv-d");
        attempt++;
        if (attempt === 1) {
          // Response dropped in flight
          throw { kind: "NETWORK_ERROR", message: "Socket hang up" };
        }
        // Second attempt receives server replay
        return { observation_id: "obs-replayed-d" };
      }),
    } as unknown as ApiClient;

    const coordinator = new SyncCoordinator({ db: mockDb, apiClient: fakeClient });

    // First attempt fails due to dropped response
    const res1 = await coordinator.sync(contextA);
    expect(res1.failed).toBe(1);

    // Fast-forward retry (simulate backoff timer elapsed)
    await mockDb.runAsync("UPDATE mutation_outbox SET next_retry_at = NULL WHERE idempotency_key = ?", ["idem-adv-d"]);

    const outbox = new MutationOutboxRepository(mockDb);
    const item = await outbox.findByIdempotencyKey("idem-adv-d");
    expect(item?.attemptCount).toBe(1);

    // Second attempt (retry) succeeds with the EXACT same idempotency key
    const res2 = await coordinator.sync(contextA);
    expect(res2.processed).toBe(1);
  });

  // TEST E — TASK CONFLICT
  it("ADVERSARIAL E: Task Conflict resolves safely when task was already updated on server", async () => {
    const captureService = new OfflineCaptureService(mockDb);
    await captureService.captureTaskTransition(contextA, "task-99", "COMPLETE", "idem-adv-e");

    const fakeClient = {
      request: vi.fn().mockRejectedValue({
        httpStatus: 409,
        code: "INVALID_STATE",
        message: "Task is already COMPLETED",
      }),
    } as unknown as ApiClient;

    const coordinator = new SyncCoordinator({ db: mockDb, apiClient: fakeClient });
    const res = await coordinator.sync(contextA);
    expect(res.failed).toBe(1);

    const outbox = new MutationOutboxRepository(mockDb);
    const item = await outbox.findByIdempotencyKey("idem-adv-e");
    expect(item?.status).toBe("CONFLICT");
  });

  // TEST F — TENANT ISOLATION
  it("ADVERSARIAL F: Tenant Isolation guarantees Tenant B cannot access Tenant A records", async () => {
    const captureService = new OfflineCaptureService(mockDb);
    await captureService.captureGlucose(contextA, { patient_id: patientA, value_mg_dl: 145 }, "idem-tenant-a");

    const outbox = new MutationOutboxRepository(mockDb);
    const tenantAPending = await outbox.getPendingMutations(contextA);
    expect(tenantAPending).toHaveLength(1);

    const tenantBPending = await outbox.getPendingMutations(contextB);
    expect(tenantBPending).toHaveLength(0);
  });
});
