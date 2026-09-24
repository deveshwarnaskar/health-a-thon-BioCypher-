/**
 * Doctor / P.L.A.T.E. query-family keys (Gate 10F-M). Server state only;
 * never persisted. Keys are stable so mutations can invalidate exactly the
 * affected families: review queue, one artifact, cohort, one patient, one
 * patient's clinician observations, and medication-plan lists/details.
 */
export const doctorKeys = {
  all: ["doctor"] as const,
  reviewQueue: () => ["doctor", "review", "queue"] as const,
  artifact: (artifactId: string) => ["doctor", "review", "artifact", artifactId] as const,
  patients: () => ["doctor", "patients"] as const,
  patient: (patientId: string) => ["doctor", "patients", patientId] as const,
  clinicianObservations: (patientId: string) => ["doctor", "observations", patientId] as const,
  medicationPlans: (patientId?: string) =>
    patientId
      ? (["doctor", "medication-plans", "patient", patientId] as const)
      : (["doctor", "medication-plans"] as const),
  medicationPlan: (planId: string) => ["doctor", "medication-plans", planId] as const,
  tasks: (patientId?: string) =>
    patientId
      ? (["doctor", "tasks", "patient", patientId] as const)
      : (["doctor", "tasks"] as const),
  documents: (patientId: string) => ["doctor", "documents", patientId] as const,
  insights: (patientId: string) => ["doctor", "insights", patientId] as const,
  notifications: (patientId?: string) =>
    patientId
      ? (["doctor", "notifications", "patient", patientId] as const)
      : (["doctor", "notifications"] as const),
  clinicalState: (patientId: string, windowDays: number = 14) =>
    ["doctor", "clinical-state", patientId, windowDays] as const,
} as const;