import React, { useState } from "react";
import { CaregiverPatientsScreen } from "./CaregiverPatientsScreen";
import { CaregiverPatientGlucoseScreen } from "./CaregiverPatientGlucoseScreen";
import type { CaregiverPatientListItem } from "../../services/schemas/caregiver";

export type CaregiverWorkflowProps = {
  /**
   * Exit the caregiver workflow entirely (back to the shell main menu).
   */
  onExit?: () => void;
  testID?: string;
};

/**
 * Caregiver mobile vertical slice state machine (online-only, Gate 10E-M).
 * The selected patient is EPHEMERAL UI state held in memory only — it is never
 * persisted, never written to a store, and never stored on disk. Every entry
 * into the workflow resolves patient selection from the authoritative
 * caregiver patient list query (["caregivers", "me", "patients"]).
 */
export function CaregiverWorkflow({ onExit, testID }: CaregiverWorkflowProps) {
  const [selectedPatient, setSelectedPatient] = useState<CaregiverPatientListItem | null>(null);

  if (selectedPatient) {
    return (
      <CaregiverPatientGlucoseScreen
        patient={selectedPatient}
        onBack={() => setSelectedPatient(null)}
        onAccessLost={() => setSelectedPatient(null)}
        testID={testID}
      />
    );
  }

  return (
    <CaregiverPatientsScreen
      onSelect={(patient) => setSelectedPatient(patient)}
      onBack={onExit}
      testID={testID}
    />
  );
}