import React from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { useCaregiverContext } from "../context/CaregiverContext";
import { AppCard } from "../../../components/primitives/AppCard";
import { Badge } from "../../../components/primitives/Badge";
import { Button } from "../../../components/primitives/Button";
import { EmptyState } from "../../../components/primitives/EmptyState";
import { ErrorState } from "../../../components/primitives/ErrorState";
import { LoadingState } from "../../../components/primitives/LoadingState";
import { colors, spacing, typography } from "../../../theming/tokens";
import {
  canReadCaregiverGlucose,
  canRecordCaregiverGlucose,
} from "../../../services/schemas/caregiver";

export type CaregiverHomeTabProps = {
  onNavigateToRecord: () => void;
  onOpenPatientSwitcher?: () => void;
  testID?: string;
};

/**
 * Caregiver Home Tab (Gate C1).
 * Shows active patient identity, relationship info, and direct pathways to Record.
 * Strictly presents only verified data returned by the backend — zero invented metrics.
 */
export function CaregiverHomeTab({
  onNavigateToRecord,
  onOpenPatientSwitcher,
  testID = "caregiver-home-tab",
}: CaregiverHomeTabProps) {
  const { activePatient, linkedPatients, isLoading, isError, selectPatient, refreshPatients } =
    useCaregiverContext();

  if (isLoading) {
    return <LoadingState label="Loading patient information…" />;
  }

  if (isError) {
    return (
      <View style={styles.stateContainer} testID={testID}>
        <ErrorState
          title="Unable to load patients"
          message="Could not load your caregiver patient record. Please try again."
          onRetry={() => refreshPatients()}
        />
      </View>
    );
  }

  if (linkedPatients.length === 0) {
    return (
      <View style={styles.stateContainer} testID={testID}>
        <EmptyState
          title="No linked patients"
          message="You are not currently authorized to view any patients. A clinic coordinator adds and verifies caregiver relationships."
        />
      </View>
    );
  }

  if (!activePatient) {
    return (
      <ScrollView style={styles.container} contentContainerStyle={styles.content} testID={testID}>
        <View style={styles.header}>
          <Text style={styles.heading} allowFontScaling>
            {"Choose who you're caring for"}
          </Text>
          <Text style={styles.subheading} allowFontScaling>
            Select an authorized patient to view their records and contribute observations.
          </Text>
        </View>

        {linkedPatients.map((patient) => (
          <AppCard
            key={patient.patient_id}
            accessibilityLabel={`Select patient ${patient.name}`}
            onPress={() => selectPatient(patient.patient_id)}
          >
            <View style={styles.patientCardHeader}>
              <Text style={styles.patientName} allowFontScaling>
                {patient.name}
              </Text>
              {patient.relationship_label ? (
                <Badge label={patient.relationship_label} tone="neutral" />
              ) : null}
            </View>

            <View style={styles.badgeRow}>
              {patient.status === "verified" ? (
                <Badge label="Verified relationship" tone="success" />
              ) : null}
            </View>

            <View style={styles.buttonWrapper}>
              <Button
                label={`Select ${patient.name}`}
                variant="outline"
                onPress={() => selectPatient(patient.patient_id)}
                accessibilityLabel={`Select patient ${patient.name}`}
              />
            </View>
          </AppCard>
        ))}
      </ScrollView>
    );
  }

  const canRead = canReadCaregiverGlucose(activePatient.capabilities);
  const canRecord = canRecordCaregiverGlucose(activePatient.capabilities);
  const hasMultiplePatients = linkedPatients.length > 1;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content} testID={testID}>
      <View style={styles.header}>
        <Text style={styles.heading} allowFontScaling>
          Active Patient
        </Text>
        <Text style={styles.subheading} allowFontScaling>
          Review records and contribute observations for your authorized patient.
        </Text>
      </View>

      <AppCard accessibilityLabel={`Active patient: ${activePatient.name}`}>
        <View style={styles.patientCardHeader}>
          <Text style={styles.patientName} allowFontScaling>
            {activePatient.name}
          </Text>
          {activePatient.relationship_label ? (
            <Badge label={activePatient.relationship_label} tone="neutral" />
          ) : null}
        </View>

        <View style={styles.badgeRow}>
          {activePatient.status === "verified" ? (
            <Badge label="Verified relationship" tone="success" />
          ) : null}
          {canRead ? <Badge label="Glucose view" tone="info" /> : null}
          {canRecord ? <Badge label="Can record" tone="success" /> : null}
        </View>
      </AppCard>

      <AppCard
        accessibilityLabel="Open patient health record"
        onPress={onNavigateToRecord}
      >
        <Text style={styles.actionTitle} allowFontScaling>
          Patient Health Record
        </Text>
        <Text style={styles.actionDescription} allowFontScaling>
          View glucose observations and submit new readings for {activePatient.name}.
        </Text>
        <View style={styles.buttonWrapper}>
          <Button label="Open Record" variant="primary" onPress={onNavigateToRecord} />
        </View>
      </AppCard>

      {hasMultiplePatients && onOpenPatientSwitcher ? (
        <AppCard
          accessibilityLabel="Switch active patient"
          onPress={onOpenPatientSwitcher}
        >
          <Text style={styles.actionTitle} allowFontScaling>
            Switch Patient ({linkedPatients.length} linked)
          </Text>
          <Text style={styles.actionDescription} allowFontScaling>
            You have access to multiple patients. Select another patient to manage their care.
          </Text>
          <View style={styles.buttonWrapper}>
            <Button
              label="Change Patient"
              variant="outline"
              onPress={onOpenPatientSwitcher}
            />
          </View>
        </AppCard>
      ) : null}
    </ScrollView>
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
    paddingBottom: spacing.xxl,
  },
  stateContainer: {
    flex: 1,
    padding: spacing.md,
    justifyContent: "center",
  },
  header: {
    gap: spacing.xxs,
  },
  heading: {
    fontSize: typography.fontSize.title,
    fontWeight: "700",
    color: colors.textPrimary,
  },
  subheading: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textSecondary,
  },
  patientCardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.xs,
  },
  patientName: {
    fontSize: typography.fontSize.title,
    fontWeight: "700",
    color: colors.textPrimary,
  },
  badgeRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs,
    marginTop: spacing.xs,
  },
  actionTitle: {
    fontSize: typography.fontSize.body,
    fontWeight: "700",
    color: colors.textPrimary,
    marginBottom: spacing.xxs,
  },
  actionDescription: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textSecondary,
    marginBottom: spacing.sm,
  },
  buttonWrapper: {
    alignItems: "flex-start",
  },
});
