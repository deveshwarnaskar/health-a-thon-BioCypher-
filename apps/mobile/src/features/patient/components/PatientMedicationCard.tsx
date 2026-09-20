import React from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { colors, radii, spacing, touchTarget, typography } from "../../../theming/tokens";
import type { MedicationPlanResponse } from "../../../services/schemas/medication";

export type PatientMedicationCardProps = {
  plan: MedicationPlanResponse;
  isTaken?: boolean;
  onMarkTaken?: (planId: string) => void;
  isMarking?: boolean;
  onPressDetail?: (plan: MedicationPlanResponse) => void;
};

export function PatientMedicationCard({
  plan,
  isTaken = false,
  onMarkTaken,
  isMarking = false,
  onPressDetail,
}: PatientMedicationCardProps) {
  return (
    <View style={styles.card} accessibilityRole="none">
      <TouchableOpacity
        onPress={() => onPressDetail?.(plan)}
        activeOpacity={0.7}
        accessibilityRole="button"
        accessibilityLabel={`${plan.medication}, instructions: ${plan.instruction || "As directed"}`}
      >
        <View style={styles.topRow}>
          <View style={styles.iconTag}>
            <Text style={styles.pillIcon} allowFontScaling>
              💊
            </Text>
          </View>
          <View
            style={[
              styles.statusBadge,
              isTaken ? styles.statusBadgeTaken : styles.statusBadgeDue,
            ]}
          >
            <Text
              style={[
                styles.statusText,
                isTaken ? styles.statusTextTaken : styles.statusTextDue,
              ]}
              allowFontScaling
            >
              {isTaken ? "✓ Taken" : "Scheduled"}
            </Text>
          </View>
        </View>

        <Text style={styles.medicationName} allowFontScaling numberOfLines={1}>
          {plan.medication}
        </Text>

        <Text style={styles.instructions} allowFontScaling numberOfLines={2}>
          {plan.instruction || "Take as prescribed by clinician"}
        </Text>

        <View style={styles.metaRow}>
          <Text style={styles.prescriberTag} allowFontScaling>
            Prescribed by {plan.prescribed_by_role || "Clinician"}
          </Text>
        </View>
      </TouchableOpacity>

      {!isTaken && onMarkTaken ? (
        <View style={styles.actionContainer}>
          <TouchableOpacity
            style={[styles.takenButton, isMarking && styles.takenButtonBusy]}
            onPress={() => onMarkTaken(plan.medication_plan_id)}
            disabled={isMarking}
            accessibilityRole="button"
            accessibilityLabel={`Mark ${plan.medication} as taken`}
            accessibilityHint="Confirms you took this medication dose"
            activeOpacity={0.8}
          >
            <Text style={styles.takenButtonText} allowFontScaling>
              {isMarking ? "Recording…" : "Mark as taken"}
            </Text>
          </TouchableOpacity>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  topRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.xs,
  },
  iconTag: {
    width: 32,
    height: 32,
    borderRadius: radii.sm,
    backgroundColor: "#F0F7F9",
    alignItems: "center",
    justifyContent: "center",
  },
  pillIcon: {
    fontSize: 16,
  },
  statusBadge: {
    paddingHorizontal: spacing.xs,
    paddingVertical: 3,
    borderRadius: radii.pill,
  },
  statusBadgeTaken: {
    backgroundColor: "#E8F8F5",
  },
  statusBadgeDue: {
    backgroundColor: "#FDF2E9",
  },
  statusText: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.weight.bold,
  },
  statusTextTaken: {
    color: colors.leafGreen,
  },
  statusTextDue: {
    color: colors.assistive,
  },
  medicationName: {
    fontSize: typography.fontSize.body,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
  },
  instructions: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textSecondary,
    marginTop: 4,
    lineHeight: typography.lineHeight.bodySmall,
  },
  metaRow: {
    marginTop: spacing.xs,
    flexDirection: "row",
    alignItems: "center",
  },
  prescriberTag: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    fontStyle: "italic",
  },
  actionContainer: {
    marginTop: spacing.sm,
    paddingTop: spacing.xs,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  takenButton: {
    backgroundColor: colors.primary,
    borderRadius: radii.md,
    minHeight: touchTarget.min,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing.md,
  },
  takenButtonBusy: {
    opacity: 0.6,
  },
  takenButtonText: {
    color: colors.textOnPrimary,
    fontSize: typography.fontSize.bodySmall,
    fontWeight: typography.weight.semibold,
  },
});
