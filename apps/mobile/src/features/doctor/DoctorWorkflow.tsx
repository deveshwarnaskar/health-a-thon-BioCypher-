import React, { useState } from "react";
import { ReviewQueueScreen } from "./ReviewQueueScreen";
import { ArtifactDetailScreen } from "./ArtifactDetailScreen";
import { PatientCohortScreen } from "./PatientCohortScreen";
import { PatientDetailScreen } from "./PatientDetailScreen";
import { CreateMedicationPlanScreen } from "./CreateMedicationPlanScreen";
import { MedicationPlansScreen } from "./MedicationPlansScreen";
import { MedicationPlanDetailScreen } from "./MedicationPlanDetailScreen";
import type {
  AIArtifactResponse,
} from "../../services/schemas/ai";
import type { PatientSummaryResponse } from "../../services/schemas/patients";
import type { MedicationPlanResponse } from "../../services/schemas/medication";

export type DoctorFlow = "review" | "patients" | "plans";

export type DoctorWorkflowProps = {
  flow: DoctorFlow;
  onHome?: () => void;
  testID?: string;
};

type View =
  | { name: "review" }
  | { name: "artifact"; artifact: AIArtifactResponse }
  | { name: "cohort" }
  | { name: "patient"; patient: PatientSummaryResponse }
  | { name: "createPlan"; patient: PatientSummaryResponse }
  | { name: "plans" }
  | { name: "plan"; plan: MedicationPlanResponse };

/**
 * Doctor / P.L.A.T.E. view-state machine (Gate 10F-M).
 *
 * Selections (artifact, patient, plan) are EPHEMERAL React state: they live
 * only for the session, are deliberately never persisted (no
 * AsyncStorage/SQLite/SecureStore/Zustand), and every underlying query still
 * hits the backend — which remains the sole authorization authority.
 */
export function DoctorWorkflow({ flow, onHome, testID }: DoctorWorkflowProps) {
  const rootView: View =
    flow === "review"
      ? { name: "review" }
      : flow === "patients"
        ? { name: "cohort" }
        : { name: "plans" };
  const [view, setView] = useState<View>(rootView);

  if (view.name === "artifact") {
    return (
      <ArtifactDetailScreen
        key={view.artifact.artifact_id}
        artifactId={view.artifact.artifact_id}
        onBack={() => setView({ name: "review" })}
        testID={testID ? `${testID}-artifact` : undefined}
      />
    );
  }

  if (view.name === "patient") {
    return (
      <PatientDetailScreen
        patient={view.patient}
        onBack={() => setView({ name: "cohort" })}
        onCreatePlan={(patient) => setView({ name: "createPlan", patient })}
        testID={testID ? `${testID}-patient` : undefined}
      />
    );
  }

  if (view.name === "createPlan") {
    return (
      <CreateMedicationPlanScreen
        patient={view.patient}
        onCancel={() => setView({ name: "patient", patient: view.patient })}
        onCreated={() => setView({ name: "patient", patient: view.patient })}
        testID={testID ? `${testID}-create-plan` : undefined}
      />
    );
  }

  if (view.name === "plan") {
    return (
      <MedicationPlanDetailScreen
        planId={view.plan.medication_plan_id}
        onBack={() => setView({ name: "plans" })}
        testID={testID ? `${testID}-plan` : undefined}
      />
    );
  }

  if (view.name === "review") {
    return (
      <ReviewQueueScreen
        onSelect={(artifact) => setView({ name: "artifact", artifact })}
        onBack={onHome}
        testID={testID ? `${testID}-queue` : undefined}
      />
    );
  }

  if (view.name === "cohort") {
    return (
      <PatientCohortScreen
        onSelect={(patient) => setView({ name: "patient", patient })}
        onBack={onHome}
        testID={testID ? `${testID}-cohort` : undefined}
      />
    );
  }

  // view.name === "plans"
  return (
    <MedicationPlansScreen
      onSelect={(plan) => setView({ name: "plan", plan })}
      onBack={onHome}
      testID={testID ? `${testID}-plans` : undefined}
    />
  );
}