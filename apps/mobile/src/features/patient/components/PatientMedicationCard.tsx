import React from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { colors, radii, spacing, touchTarget, typography } from "../../../theming/tokens";
import type { MedicationPlanResponse } from "../../../services/schemas/medication";

export type MedicationAdherenceAction = "NOW" | "ON_TIME" | "SKIPPED" | "SNOOZE";

export type PatientMedicationCardProps = {
  plan: MedicationPlanResponse;
  isTaken?: boolean;
  adherenceStatus?: "TAKEN" | "SKIPPED" | "SNOOZED" | null;
  onMarkTaken?: (planId: string, action?: MedicationAdherenceAction, administeredAt?: string) => void;
  isMarking?: boolean;
  onPressDetail?: (plan: MedicationPlanResponse) => void;
};

export function PatientMedicationCard({
  plan,
  isTaken = false,
  adherenceStatus,
  onMarkTaken,
  isMarking = false,
  onPressDetail,
}: PatientMedicationCardProps) {
  const currentStatus = adherenceStatus ?? (isTaken ? "TAKEN" : null);

  const renderBadge = () => {
    if (currentStatus === "TAKEN") {
      return (
        <View style={[styles.statusBadge, styles.statusBadgeTaken]}>
          <Text style={[styles.statusText, styles.statusTextTaken]} allowFontScaling>
            ✓ Taken
          </Text>
        </View>
      );
    }
    if (currentStatus === "SKIPPED") {
      return (
        <View style={[styles.statusBadge, styles.statusBadgeSkipped]}>
          <Text style={[styles.statusText, styles.statusTextSkipped]} allowFontScaling>
            Skipped
          </Text>
        </View>
      );
    }
    if (currentStatus === "SNOOZED") {
      return (
        <View style={[styles.statusBadge, styles.statusBadgeSnoozed]}>
          <Text style={[styles.statusText, styles.statusTextSnoozed]} allowFontScaling>
            Snoozed (15m)
          </Text>
        </View>
      );
    }
    return (
      <View style={[styles.statusBadge, styles.statusBadgeDue]}>
        <Text style={[styles.statusText, styles.statusTextDue]} allowFontScaling>
          Scheduled
        </Text>
      </View>
    );
  };

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
          {renderBadge()}
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

      {!currentStatus && onMarkTaken ? (
        <View style={styles.actionContainer}>
          <TouchableOpacity
            style={[styles.takenButton, isMarking && styles.takenButtonBusy]}
            onPress={() => onMarkTaken(plan.medication_plan_id, "NOW")}
            disabled={isMarking}
            accessibilityRole="button"
            accessibilityLabel={`Took ${plan.medication} just now`}
            accessibilityHint="Records medication dose as taken now"
            activeOpacity={0.8}
          >
            <Text style={styles.takenButtonText} allowFontScaling>
              {isMarking ? "Recording…" : "Took just now"}
            </Text>
          </TouchableOpacity>

          <View style={styles.secondaryActionsRow}>
            <TouchableOpacity
              style={styles.secondaryActionBtn}
              onPress={() => {
                // Scheduled dose 1 hour ago
                const onTimeIso = new Date(Date.now() - 3600000).toISOString();
                onMarkTaken(plan.medication_plan_id, "ON_TIME", onTimeIso);
              }}
              disabled={isMarking}
              accessibilityRole="button"
              accessibilityLabel={`Took ${plan.medication} on time`}
            >
              <Text style={styles.secondaryActionText} allowFontScaling>
                Took on time
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.secondaryActionBtn}
              onPress={() => onMarkTaken(plan.medication_plan_id, "SKIPPED")}
              disabled={isMarking}
              accessibilityRole="button"
              accessibilityLabel={`Skip dose for ${plan.medication}`}
            >
              <Text style={styles.secondaryActionText} allowFontScaling>
                Skip dose
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.secondaryActionBtn}
              onPress={() => onMarkTaken(plan.medication_plan_id, "SNOOZE")}
              disabled={isMarking}
              accessibilityRole="button"
              accessibilityLabel={`Snooze reminder for ${plan.medication}`}
            >
              <Text style={styles.secondaryActionText} allowFontScaling>
                Snooze 15m
              </Text>
            </TouchableOpacity>
          </View>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: "#FFFFFF",
    padding: spacing.md,
    marginBottom: spacing.sm,
    shadowColor: colors.primaryInk,
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.07,
    shadowRadius: 16,
    elevation: 2,
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
    borderRadius: radii.pill,
    backgroundColor: colors.tileAqua,
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
    backgroundColor: colors.tileGreen,
  },
  statusBadgeDue: {
    backgroundColor: colors.tileCream,
  },
  statusBadgeSkipped: {
    backgroundColor: colors.backgroundRaised,
  },
  statusBadgeSnoozed: {
    backgroundColor: colors.tileYellow,
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
  statusTextSkipped: {
    color: colors.textSecondary,
  },
  statusTextSnoozed: {
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
    borderRadius: radii.pill,
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
  secondaryActionsRow: {
    flexDirection: "row",
    gap: spacing.xs,
    marginTop: spacing.xs,
  },
  secondaryActionBtn: {
    flex: 1,
    paddingVertical: spacing.xs,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  secondaryActionText: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.weight.medium,
    color: colors.textSecondary,
  },
});
