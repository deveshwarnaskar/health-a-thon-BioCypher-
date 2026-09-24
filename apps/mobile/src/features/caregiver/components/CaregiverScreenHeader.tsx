import React, { useState } from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { useCaregiverContext } from "../context/CaregiverContext";
import { CaregiverPatientSwitcher } from "./CaregiverPatientSwitcher";
import { colors, radii, spacing, touchTarget, typography } from "../../../theming/tokens";

export type CaregiverScreenHeaderProps = {
  testID?: string;
};

/**
 * Caregiver screen header.
 * Displays THALI, Caregiver role, and "Caring for [patient name]".
 * If multiple linked patients exist, provides a safe patient switch control.
 * Strictly avoids carbohydrate grams, glycemic index, doctor analytics, and diagnostic labels.
 */
export function CaregiverScreenHeader({ testID = "caregiver-screen-header" }: CaregiverScreenHeaderProps) {
  const { activePatient, linkedPatients } = useCaregiverContext();
  const [switcherOpen, setSwitcherOpen] = useState(false);

  const hasMultiplePatients = linkedPatients.length > 1;

  return (
    <View style={styles.container} testID={testID}>
      <View style={styles.brandRow}>
        <View style={styles.brandGroup}>
          <Text style={styles.brandTitle} allowFontScaling>
            THALI
          </Text>
          <Text style={styles.roleLabel} allowFontScaling>
            Caregiver
          </Text>
        </View>

        {activePatient ? (
          <View style={styles.patientContextContainer}>
            <Text style={styles.caringForLabel} allowFontScaling>
              Caring for
            </Text>
            <View style={styles.activePatientRow}>
              <Text style={styles.patientName} numberOfLines={1} allowFontScaling>
                {activePatient.name}
              </Text>
              {hasMultiplePatients ? (
                <TouchableOpacity
                  style={styles.switchButton}
                  onPress={() => setSwitcherOpen(true)}
                  accessibilityRole="button"
                  accessibilityLabel="Switch active patient"
                  accessibilityHint="Opens list of authorized patients"
                >
                  <Text style={styles.switchButtonText} allowFontScaling>
                    Switch
                  </Text>
                </TouchableOpacity>
              ) : null}
            </View>
          </View>
        ) : null}
      </View>

      {hasMultiplePatients ? (
        <CaregiverPatientSwitcher
          visible={switcherOpen}
          onClose={() => setSwitcherOpen(false)}
        />
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  brandRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    minHeight: 48,
  },
  brandGroup: {
    justifyContent: "center",
  },
  brandTitle: {
    fontSize: typography.fontSize.title,
    fontWeight: "800",
    color: colors.primary,
    letterSpacing: 0.5,
  },
  roleLabel: {
    fontSize: typography.fontSize.caption,
    fontWeight: "600",
    color: colors.textSecondary,
    textTransform: "uppercase",
    letterSpacing: 0.8,
  },
  patientContextContainer: {
    alignItems: "flex-end",
    flexShrink: 1,
    marginLeft: spacing.sm,
  },
  caringForLabel: {
    fontSize: 11,
    color: colors.textSecondary,
    fontWeight: "500",
  },
  activePatientRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
  },
  patientName: {
    fontSize: typography.fontSize.body,
    fontWeight: "700",
    color: colors.textPrimary,
    maxWidth: 160,
  },
  switchButton: {
    backgroundColor: "rgba(13, 148, 136, 0.12)",
    paddingHorizontal: spacing.xs,
    paddingVertical: 2,
    borderRadius: radii.sm,
    minHeight: touchTarget.min,
    justifyContent: "center",
  },
  switchButtonText: {
    fontSize: 12,
    fontWeight: "700",
    color: colors.primary,
  },
});
