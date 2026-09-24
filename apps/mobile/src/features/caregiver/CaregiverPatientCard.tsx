import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { AppCard } from "../../components/primitives/AppCard";
import { Badge } from "../../components/primitives/Badge";
import { colors, spacing, typography } from "../../theming/tokens";
import {
  canReadCaregiverGlucose,
  canRecordCaregiverGlucose,
  type CaregiverPatientListItem,
} from "../../services/schemas/caregiver";

export type CaregiverPatientCardProps = {
  patient: CaregiverPatientListItem;
  onSelect: (patient: CaregiverPatientListItem) => void;
  disabled?: boolean;
};

/**
 * One authorized patient entry in the caregiver discovery list. Only
 * relationship selection facts are rendered (Gate 10E-B §2); no clinical data.
 */
export function CaregiverPatientCard({
  patient,
  onSelect,
  disabled = false,
}: CaregiverPatientCardProps) {
  const canRead = canReadCaregiverGlucose(patient.capabilities);
  const canRecord = canRecordCaregiverGlucose(patient.capabilities);

  return (
    <AppCard
      accessibilityLabel={`View glucose for ${patient.name}`}
      onPress={disabled ? undefined : () => onSelect(patient)}
      style={disabled ? styles.disabled : undefined}
    >
      <View style={styles.header}>
        <Text style={styles.name} allowFontScaling>
          {patient.name}
        </Text>
        {patient.relationship_label ? (
          <Badge label={patient.relationship_label} tone="neutral" />
        ) : null}
      </View>
      <View style={styles.badgeRow}>
        {canRead ? <Badge label="Glucose view" tone="info" /> : null}
        {canRecord ? <Badge label="Can record" tone="success" /> : null}
      </View>
    </AppCard>
  );
}

const styles = StyleSheet.create({
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: spacing.sm,
  },
  name: {
    flexShrink: 1,
    fontSize: typography.fontSize.body,
    fontWeight: "600",
    color: colors.textPrimary,
  },
  badgeRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs,
  },
  disabled: {
    opacity: 0.5,
  },
});