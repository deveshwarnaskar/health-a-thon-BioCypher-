import { localDatabase } from "../../db/database";
import { localSessionIsolation } from "../../db/isolation";
import { secureUuid } from "../../services/api/correlation";
import type { TimelineEvent, TimelineEventType } from "./types";

export type SecondaryEventInput = {
  patientId: string;
  type: TimelineEventType;
  title: string;
  subtitle: string;
  timestamp: string;
  details?: Record<string, any>;
};

// In-memory cache ensures seamless operation across Web/Native and during session restoration
const inMemorySecondaryEvents: (TimelineEvent & { patientId: string })[] = [];

let tableInitialized = false;

export function clearSecondaryStorageForTesting() {
  inMemorySecondaryEvents.length = 0;
  tableInitialized = false;
}

async function ensureTable() {
  if (tableInitialized) return;
  if (!localDatabase.isOpen()) return;
  try {
    const db = localDatabase.getDb();
    await db.execAsync(`
      CREATE TABLE IF NOT EXISTS local_secondary_events (
        id TEXT PRIMARY KEY,
        patient_id TEXT NOT NULL,
        event_type TEXT NOT NULL,
        title TEXT NOT NULL,
        subtitle TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        details_json TEXT NOT NULL,
        created_at TEXT NOT NULL
      );
    `);
    tableInitialized = true;
  } catch {
    // Non-fatal if sqlite execution is unavailable
  }
}

export async function saveSecondaryEvent(input: SecondaryEventInput): Promise<TimelineEvent> {
  const id = `local-${input.type}-${secureUuid()}`;
  const nowIso = new Date().toISOString();

  const event: TimelineEvent = {
    id,
    type: input.type,
    title: input.title,
    subtitle: input.subtitle,
    timestamp: input.timestamp || nowIso,
    status: "SAVED_LOCALLY",
    details: input.details,
  };

  inMemorySecondaryEvents.unshift({ ...event, patientId: input.patientId });

  try {
    await ensureTable();
    if (localDatabase.isOpen()) {
      const db = localDatabase.getDb();
      await db.runAsync(
        `INSERT OR REPLACE INTO local_secondary_events 
         (id, patient_id, event_type, title, subtitle, timestamp, details_json, created_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
        [
          id,
          input.patientId,
          input.type,
          input.title,
          input.subtitle,
          input.timestamp || nowIso,
          JSON.stringify(input.details || {}),
          nowIso,
        ]
      );
    }
  } catch {
    // Graceful fallback to memory store
  }

  return event;
}

export async function getSecondaryEvents(
  patientId?: string | null,
  typeFilter?: TimelineEventType
): Promise<TimelineEvent[]> {
  const memoryScoped = patientId
    ? inMemorySecondaryEvents
        .filter((e) => e.patientId === patientId)
        .map(({ patientId: _, ...rest }) => rest)
    : inMemorySecondaryEvents.map(({ patientId: _, ...rest }) => rest);

  let results: TimelineEvent[] = [...memoryScoped];
  const seenIds = new Set(results.map((r) => r.id));

  try {
    await ensureTable();
    if (localDatabase.isOpen()) {
      const db = localDatabase.getDb();
      const rows = await db.getAllAsync<{
        id: string;
        event_type: string;
        title: string;
        subtitle: string;
        timestamp: string;
        details_json: string;
      }>(
        "SELECT id, event_type, title, subtitle, timestamp, details_json FROM local_secondary_events WHERE patient_id = ? ORDER BY timestamp DESC",
        [patientId]
      );

      for (const row of rows) {
        if (!seenIds.has(row.id)) {
          seenIds.add(row.id);
          let details = {};
          try {
            details = JSON.parse(row.details_json);
          } catch {}
          results.push({
            id: row.id,
            type: row.event_type as TimelineEventType,
            title: row.title,
            subtitle: row.subtitle,
            timestamp: row.timestamp,
            status: "SAVED_LOCALLY",
            details,
          });
        }
      }
    }
  } catch {
    // Memory store used on read failure
  }

  if (typeFilter) {
    results = results.filter((r) => r.type === typeFilter);
  }

  results.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
  return results;
}
