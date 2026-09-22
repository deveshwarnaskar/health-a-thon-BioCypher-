import type { PatientGlucoseObservation } from "../glucose/types";
import type { PatientMealObservation } from "../meals/types";
import type { MedicationPlanResponse } from "../../services/schemas/medication";
import type { CareTaskResponse } from "../../services/schemas/tasks";

export type PatientTab = "home" | "record" | "timeline" | "tasks" | "you";

export type TimelineFilter =
  | "all"
  | "glucose"
  | "meals"
  | "medication"
  | "activity"
  | "vitals"
  | "symptoms"
  | "sleep"
  | "tasks"
  | "documents";

export type TimelineEventType =
  | "glucose"
  | "meal"
  | "medication"
  | "task"
  | "document"
  | "activity"
  | "vital"
  | "symptom"
  | "sleep";

export type TimelineEvent = {
  id: string;
  type: TimelineEventType;
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
  extracted_data?: {
    hba1c?: number;
    fasting_glucose?: number;
    cholesterol?: number;
    detected_at?: string;
    confirmed_by_patient?: boolean;
  };
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
  activity?: {
    recordedTodayCount: number;
    totalMinutesToday: number;
  };
  tasks?: {
    totalToday: number;
    completedToday: number;
    pendingCount: number;
  };
  dataCompletenessPct: number;
  attentionCount: number;
};

export type CareProfileData = {
  diabetesType: string;
  activeCarePlan: string;
  glucoseMonitoringMethod: string;
  targetRange: {
    fastingLow: number;
    fastingHigh: number;
    postMealHigh: number;
  };
  trackingEnabled: {
    glucose: boolean;
    meals: boolean;
    medication: boolean;
    activity: boolean;
    bloodPressure: boolean;
    weight: boolean;
  };
  reportSchedule: string;
  careTeam: {
    doctorName: string;
    facilityName: string;
    carePlanId: string;
  };
};

export type EvidenceItem = {
  id: string;
  date: string;
  time: string;
  type: "glucose" | "meal" | "activity" | "medication";
  label: string;
  value: string;
  context?: string;
};

export type WeeklyReportData = {
  id: string;
  weekNumber: number;
  dateRange: string;
  status: "ready" | "generating" | "upcoming";
  sharingStatus: "shared" | "not_shared";
  sharedWithDoctorName?: string;
  generatedAt?: string;
  dataCoverage: {
    loggedDays: number;
    totalDays: number;
    percentage: number;
  };
  glucoseMetrics: {
    averageMgDl: number | null;
    totalReadings: number;
    fastingAverageMgDl: number | null;
    postMealAverageMgDl: number | null;
    timeInRangePct: number | null; // 70-180 mg/dL
    timeAboveRangePct: number | null;
    timeBelowRangePct: number | null;
    gmiPct: number | null;
  };
  mealsSummary: {
    totalLogged: number;
    daysWithMeals: number;
  };
  medicationAdherence: {
    scheduledDoses: number;
    takenDoses: number;
    adherencePct: number;
    missedDoses: number;
  };
  activitySummary: {
    activeDays: number;
    totalMinutes: number;
  };
  symptomsCount: number;
  observedPatterns: {
    title: string;
    observationText: string;
    evidenceText: string;
    evidenceItems: EvidenceItem[];
  }[];
  contextualLimitations: string;
  clinicianQuestions: string[];
};

export type MonthlyReportData = {
  id: string;
  monthName: string;
  year: number;
  status: "ready" | "generating" | "upcoming";
  sharingStatus: "shared" | "not_shared";
  sharedWithDoctorName?: string;
  generatedAt?: string;
  dataCoverageDays: number;
  glucoseTrend: {
    week1Avg: number | null;
    week2Avg: number | null;
    week3Avg: number | null;
    week4Avg: number | null;
  };
  averageGlucoseMgDl: number | null;
  totalReadings: number;
  medicationAdherencePct: number;
  totalMealsLogged: number;
  totalActiveMinutes: number;
  repeatedObservations: string[];
  clinicianDiscussionTopics: string[];
  evidenceItems: EvidenceItem[];
};
