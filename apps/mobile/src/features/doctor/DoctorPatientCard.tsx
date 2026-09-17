import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { AppCard } from "../../components/primitives/AppCard";
import { Badge } from "../../components/primitives/Badge";
import { colors, spacing, typography } from "../../theming/tokens";
import type { PatientSummaryResponse } from "../../services/schemas/patients";

export type DoctorPatientCardProps = {
  patient: PatientSummaryResponse;
  onSelect: (patient: PatientSummaryResponse) => void;
  disabled?: boolean;
};

/**
 * One patient in the clinician cohort. Identity/lifecycle facts only — no
 * clinical analytics; the patient-specific surfaces load separately and are
 * independently authorized by the backend.
 */
export function DoctorPatientCard({ patient, onSelect, disabled = false }: DoctorPatientCardProps) {
  return (
    <AppCard
      accessibilityLabel={`View patient ${patient.name}`}
      onPress={disabled ? undefined : () => onSelect(patient)}
      style={disabled ? styles.disabled : undefined}
    >
      <View style={styles.header}>
        <Text style={styles.name} numberOfLines={1} allowFontScaling>
          {patient.name}
        </Text>
        {patient.active ? <Badge label="Active" tone="success" /> : <Badge label="Inactive" tone="critical" />}
      </View>
      <Text style={styles.meta} allowFontScaling>
        UH ID {patient.uh_id}
      </Text>
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
  meta: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
  },
  disabled: {
    opacity: 0.5,
  },
});