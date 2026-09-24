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
import { CaregiverPatientCard } from "./CaregiverPatientCard";
import { useCaregiverPatients } from "./useCaregiverPatients";
import type { CaregiverPatientListItem } from "../../services/schemas/caregiver";

export type CaregiverPatientsScreenProps = {
  onSelect?: (patient: CaregiverPatientListItem) => void;
  onBack?: () => void;
  testID?: string;
};

/**
 * Caregiver patient discovery screen (Gate 10E-M). Lists only the verified,
 * active patients the backend authorizes this caregiver to select — never a
 * search or the full tenant roster.
 */
export function CaregiverPatientsScreen({
  onSelect,
  onBack,
  testID,
}: CaregiverPatientsScreenProps) {
  const { state } = useAuth();
  const authUser = state.name === "authenticated" ? state.user : null;
  const isCaregiverRole = authUser?.role === "Caregiver";

  const list = useCaregiverPatients({ enabled: isCaregiverRole });

  if (!isCaregiverRole) {
    return (
      <View style={styles.container} testID={testID}>
        <TopAppBar
          title="Patients"
          onBack={onBack}
          leadingLabel={onBack ? "Back" : undefined}
        />
        <View style={styles.content}>
          <AlertBanner
            tone="critical"
            title="Access Restricted"
            message="The patient discovery screen is only available in Caregiver mode."
          />
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
        title="My Patients"
        onBack={onBack}
        leadingLabel={onBack ? "Back" : undefined}
      />

      {list.isLoading ? <LoadingState label="Loading your patients…" /> : null}

      {!list.isLoading && list.isError ? (
        <View style={styles.content}>
          <ErrorState
            title="Could not load patients"
            message="Unable to connect to your caregiver record. Please try again."
            onRetry={() => list.refetch()}
          />
        </View>
      ) : null}

      {!list.isLoading && !list.isError && list.patients.length === 0 ? (
        <View style={styles.content}>
          <EmptyState
            title="No authorized patients"
            message="You are not currently authorized to view any patients. A clinic coordinator adds and verifies caregiver relationships."
          />
        </View>
      ) : null}

      {!list.isLoading && !list.isError && list.patients.length > 0 ? (
        <ScrollView contentContainerStyle={styles.listContent}>
          {list.patients.map((patient) => (
            <CaregiverPatientCard
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