import React from "react";
import { ScrollView, StyleSheet, View } from "react-native";
import { useAuth } from "../../auth/AuthProvider";
import { TopAppBar } from "../../components/primitives/TopAppBar";
import { AlertBanner } from "../../components/primitives/AlertBanner";
import { Button } from "../../components/primitives/Button";
import { EmptyState } from "../../components/primitives/EmptyState";
import { ErrorState } from "../../components/primitives/ErrorState";
import { LoadingState } from "../../components/primitives/LoadingState";
import { colors, spacing } from "../../theming/tokens";
import { usePatients } from "./usePatients";
import { DoctorPatientCard } from "./DoctorPatientCard";
import type { PatientSummaryResponse } from "../../services/schemas/patients";
import type { ApiErrorDetails } from "../../services/api/errors";

export type PatientCohortScreenProps = {
  onSelect?: (patient: PatientSummaryResponse) => void;
  onBack?: () => void;
  testID?: string;
};

/**
 * Doctor patient cohort (Gate 10F-M). Lists the active patients the backend
 * authorizes for the authenticated member's facility. Selection is ephemeral
 * React state — the backend re-authorizes every patient-specific request.
 */
export function PatientCohortScreen({ onSelect, onBack, testID }: PatientCohortScreenProps) {
  const { state } = useAuth();
  const authUser = state.name === "authenticated" ? state.user : null;
  const isDoctorRole = authUser?.role === "Doctor";

  const patients = usePatients({ enabled: isDoctorRole });

  if (!isDoctorRole) {
    return (
      <View style={styles.container} testID={testID}>
        <TopAppBar title="Patients" onBack={onBack} leadingLabel={onBack ? "Back" : undefined} />
        <View style={styles.content}>
          <AlertBanner
            tone="critical"
            title="Access Restricted"
            message="Patient management is only available in Doctor mode."
          />
          {onBack ? (
            <Button label="Return to Main Menu" variant="primary" onPress={onBack} />
          ) : null}
        </View>
      </View>
    );
  }

  if (patients.isError && (patients.error as ApiErrorDetails | undefined)?.httpStatus === 403) {
    return (
      <View style={styles.container} testID={testID}>
        <TopAppBar title="Patients" onBack={onBack} leadingLabel={onBack ? "Back" : undefined} />
        <View style={styles.content}>
          <View testID="doctor-cohort-access-revoked">
            <EmptyState
              title="Access Revoked"
              message="Your access to this facility's patient cohort was removed or expired. Returning to the main menu."
            />
          </View>
          {onBack ? (
            <Button label="Return to Main Menu" variant="primary" onPress={onBack} />
          ) : null}
        </View>
      </View>
    );
  }

  return (
    <View style={styles.container} testID={testID}>
      <TopAppBar
        title="Patients"
        onBack={onBack}
        leadingLabel={onBack ? "Back" : undefined}
      />

      {patients.isLoading ? <LoadingState label="Loading patients…" /> : null}

      {!patients.isLoading && patients.isError ? (
        <View style={styles.content}>
          <ErrorState
            title="Could not load patients"
            message="Unable to connect to the patient cohort. Please try again."
            onRetry={() => patients.refetch()}
          />
        </View>
      ) : null}

      {!patients.isLoading && !patients.isError && patients.patients.length === 0 ? (
        <View style={styles.content}>
          <EmptyState
            title="No active patients"
            message="There are no active patients in your facility's cohort right now."
          />
        </View>
      ) : null}

      {!patients.isLoading && !patients.isError && patients.patients.length > 0 ? (
        <ScrollView contentContainerStyle={styles.listContent}>
          {patients.patients.map((patient) => (
            <DoctorPatientCard
              key={patient.patient_id}
              patient={patient}
              onSelect={(selected) => onSelect?.(selected)}
            />
          ))}
        </ScrollView>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: spacing.md,
    gap: spacing.md,
  },
  listContent: {
    padding: spacing.md,
    gap: spacing.sm,
    paddingBottom: spacing.xxl,
  },
});