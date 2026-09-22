/**
 * Sync Lifecycle Controller (Section 3, 10, 30, 31).
 *
 * Coordinates:
 * 1. Encrypted SQLCipher SQLite initialization upon authenticated session.
 * 2. Automatic synchronization triggers on auth restore, reconnection, or manual pull-to-refresh.
 * 3. Outbox processing via SyncCoordinator.
 * 4. Transparent telemetry and offline durability.
 */

import { useEffect, useRef, useState } from "react";
import { localDatabase } from "../db/database";
import { localSessionIsolation } from "../db/isolation";
import { connectivityService } from "../connectivity/connectivityService";
import { apiClient } from "../services/api/client";
import { SyncCoordinator, type SyncTelemetryEvent } from "./syncCoordinator";
import { useAuth } from "../auth/AuthProvider";

let activeCoordinator: SyncCoordinator | null = null;

export function getSyncCoordinator(): SyncCoordinator | null {
  if (activeCoordinator) return activeCoordinator;
  if (localDatabase.isOpen()) {
    activeCoordinator = new SyncCoordinator({
      db: localDatabase.getDb(),
      apiClient,
    });
  }
  return activeCoordinator;
}

export async function triggerManualSync(): Promise<{ processed: number; failed: number } | null> {
  if (!localDatabase.isOpen() || !localSessionIsolation.hasContext()) {
    return null;
  }
  const coordinator = getSyncCoordinator();
  if (!coordinator) return null;

  const context = localSessionIsolation.getContext();
  return await coordinator.sync(context);
}

export function useSyncLifecycle() {
  const { state } = useAuth();
  const [isSyncing, setIsSyncing] = useState(false);
  const [lastSyncResult, setLastSyncResult] = useState<{
    processed: number;
    failed: number;
    timestamp: string;
  } | null>(null);

  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (state.name !== "authenticated") return;

    let cancel = false;

    async function initDatabaseAndSync() {
      // 1. Ensure SQLCipher local database is open
      if (!localDatabase.isOpen()) {
        try {
          await localDatabase.open();
        } catch (err) {
          console.warn("[syncLifecycle] Failed to initialize local encrypted database:", err);
          return;
        }
      }

      if (cancel || !localSessionIsolation.hasContext()) return;

      const coordinator = getSyncCoordinator();
      if (!coordinator) return;

      // 2. Wire up automatic sync on network reconnection
      connectivityService.setOnReconnect(async () => {
        if (!localSessionIsolation.hasContext()) return;
        const ctx = localSessionIsolation.getContext();
        try {
          if (mountedRef.current) setIsSyncing(true);
          const res = await coordinator.sync(ctx);
          if (mountedRef.current) {
            setLastSyncResult({
              ...res,
              timestamp: new Date().toISOString(),
            });
          }
        } finally {
          if (mountedRef.current) setIsSyncing(false);
        }
      });

      // 3. Listen to telemetry
      const unsubscribeTelemetry = coordinator.addTelemetryListener(
        (event: SyncTelemetryEvent) => {
          if (event.event === "sync_started" && mountedRef.current) {
            setIsSyncing(true);
          } else if (
            (event.event === "sync_completed" || event.event === "sync_failed") &&
            mountedRef.current
          ) {
            setIsSyncing(false);
          }
        }
      );

      // 4. Trigger initial sync if online
      if (connectivityService.isOnline()) {
        const ctx = localSessionIsolation.getContext();
        try {
          if (mountedRef.current) setIsSyncing(true);
          const res = await coordinator.sync(ctx);
          if (mountedRef.current) {
            setLastSyncResult({
              ...res,
              timestamp: new Date().toISOString(),
            });
          }
        } catch (err) {
          console.warn("[syncLifecycle] Initial sync encountered error:", err);
        } finally {
          if (mountedRef.current) setIsSyncing(false);
        }
      }

      return () => {
        unsubscribeTelemetry();
      };
    }

    void initDatabaseAndSync();

    return () => {
      cancel = true;
    };
  }, [state.name]);

  return {
    isSyncing,
    lastSyncResult,
    triggerSync: triggerManualSync,
  };
}
