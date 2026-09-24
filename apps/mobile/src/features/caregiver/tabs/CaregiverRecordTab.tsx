import React from "react";
import { StyleSheet, View } from "react-native";
import { useCaregiverContext } from "../context/CaregiverContext";
import { CaregiverPatientGlucoseScreen } from "../CaregiverPatientGlucoseScreen";
import { EmptyState } from "../../../components/primitives/EmptyState";
import { colors, spacing } from "../../../theming/tokens";

export type CaregiverRecordTabProps = {
  onBack?: () => void;
  testID?: string;
};

/**
 * Caregiver Record Tab (Gate C1).
 * Reuses the existing CaregiverPatientGlucoseScreen for the active patient from CaregiverContext.
 * If no active patient is selected, displays an EmptyState.
 * When access is lost (403), refetches authorized patients without logging out.
 */
export function CaregiverRecordTab({ onBack, testID = "caregiver-record-tab" }: CaregiverRecordTabProps) {
  const { activePatient, clearActivePatient, refreshPatients } = useCaregiverContext();

  if (!activePatient) {
    return (
      <View style={styles.container} testID={testID}>
        <View style={styles.emptyContainer}>
          <EmptyState
            title="No active patient"
            message="Select an authorized patient to view and record observations."
          />
        </View>
      </View>
    );
  }

  return (
    <View style={styles.container} testID={testID}>
      <CaregiverPatientGlucoseScreen
        patient={activePatient}
        onBack={onBack}
        onAccessLost={() => {
          clearActivePatient();
          void refreshPatients();
          onBack?.();
        }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  emptyContainer: {
    flex: 1,
    padding: spacing.md,
    justifyContent: "center",
  },
});
