import type { PatientGlucoseObservation } from "../glucose/types";
import type { PatientMealObservation } from "../meals/types";
import type { MedicationPlanResponse } from "../../services/schemas/medication";
import type { CareTaskResponse } from "../../services/schemas/tasks";

export type PatientTab = "home" | "record" | "timeline" | "tasks" | "you";

export type TimelineFilter = "all" | "glucose" | "meals" | "medication" | "tasks" | "documents";

export type TimelineEvent = {
  id: string;
  type: "glucose" | "meal" | "medication" | "task" | "document";
  title: string;
  subtitle: string;
  timestamp: string; // ISO 8601
  status?: "SYNCED" | "SAVED_LOCALLY" | "PENDING" | "SYNCING" | "FAILED";
  details?: Record<string, any>;
  raw?: PatientGlucoseObservation | PatientMealObservation | MedicationPlanResponse | CareTaskResponse;
};

export type PatientDocument = {
  id: string;
  patient_id: string;
  kind: string;
  filename: string;
  mime_type: string;
  file_size_bytes?: number;
  created_at: string;
  download_url?: string | null;
};

export type PatientSummaryState = {
  glucose?: {
    latestValue?: number;
    latestContext?: string;
    latestTime?: string;
    readingCountToday: number;
  };
  meals?: {
    recordedTodayCount: number;
    latestMealType?: string;
    latestTime?: string;
  };
  medication?: {
    totalPrescribed: number;
    takenTodayCount: number;
    nextDue?: {
      name: string;
      time: string;
      planId: string;
    };
  };
  tasks?: {
    totalToday: number;
    completedToday: number;
    pendingCount: number;
  };
  attentionCount: number;
};
