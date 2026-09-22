import React from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
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
          <Ionicons name="checkmark-circle" size={12} color="#059669" style={{ marginRight: 3 }} />
          <Text style={[styles.statusText, styles.statusTextTaken]} allowFontScaling>
            Taken
          </Text>
        </View>
      );
    }
    if (currentStatus === "SKIPPED") {
      return (
        <View style={[styles.statusBadge, styles.statusBadgeSkipped]}>
          <Ionicons name="close-circle" size={12} color="#64748B" style={{ marginRight: 3 }} />
          <Text style={[styles.statusText, styles.statusTextSkipped]} allowFontScaling>
            Skipped
          </Text>
        </View>
      );
    }
    if (currentStatus === "SNOOZED") {
      return (
        <View style={[styles.statusBadge, styles.statusBadgeSnoozed]}>
          <Ionicons name="alarm-outline" size={12} color="#D97706" style={{ marginRight: 3 }} />
          <Text style={[styles.statusText, styles.statusTextSnoozed]} allowFontScaling>
            Snoozed (15m)
          </Text>
        </View>
      );
    }
    return (
      <View style={[styles.statusBadge, styles.statusBadgeDue]}>
        <Ionicons name="time-outline" size={12} color="#D97706" style={{ marginRight: 3 }} />
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
            <Ionicons name="medkit" size={17} color="#2563EB" />
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
          <Ionicons name="medical-outline" size={12} color="#64748B" style={{ marginRight: 4 }} />
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
            <Ionicons name="checkmark" size={16} color="#FFFFFF" style={{ marginRight: 6 }} />
            <Text style={styles.takenButtonText} allowFontScaling>
              {isMarking ? "Recording…" : "Took just now"}
            </Text>
          </TouchableOpacity>

          <View style={styles.secondaryActionsRow}>
            <TouchableOpacity
              style={styles.secondaryActionBtn}
              onPress={() => {
                const onTimeIso = new Date(Date.now() - 3600000).toISOString();
                onMarkTaken(plan.medication_plan_id, "ON_TIME", onTimeIso);
              }}
              disabled={isMarking}
              accessibilityRole="button"
              accessibilityLabel={`Took ${plan.medication} on time`}
              activeOpacity={0.7}
            >
              <Ionicons name="time-outline" size={13} color="#475569" style={{ marginRight: 3 }} />
              <Text style={styles.secondaryActionText} allowFontScaling>
                On time
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.secondaryActionBtn}
              onPress={() => onMarkTaken(plan.medication_plan_id, "SKIPPED")}
              disabled={isMarking}
              accessibilityRole="button"
              accessibilityLabel={`Skip dose for ${plan.medication}`}
              activeOpacity={0.7}
            >
              <Ionicons name="close-outline" size={13} color="#475569" style={{ marginRight: 3 }} />
              <Text style={styles.secondaryActionText} allowFontScaling>
                Skip
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.secondaryActionBtn}
              onPress={() => onMarkTaken(plan.medication_plan_id, "SNOOZE")}
              disabled={isMarking}
              accessibilityRole="button"
              accessibilityLabel={`Snooze reminder for ${plan.medication}`}
              activeOpacity={0.7}
            >
              <Ionicons name="alarm-outline" size={13} color="#475569" style={{ marginRight: 3 }} />
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
    borderRadius: 20,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    padding: spacing.md,
    marginBottom: spacing.sm,
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 12,
    elevation: 2,
  },
  topRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.xs,
  },
  iconTag: {
    width: 36,
    height: 36,
    borderRadius: 10,
    backgroundColor: "#EFF6FF",
    alignItems: "center",
    justifyContent: "center",
  },
  statusBadge: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radii.pill,
  },
  statusBadgeTaken: {
    backgroundColor: "#ECFDF5",
  },
  statusBadgeDue: {
    backgroundColor: "#FEF3C7",
  },
  statusBadgeSkipped: {
    backgroundColor: "#F1F5F9",
  },
  statusBadgeSnoozed: {
    backgroundColor: "#FEF3C7",
  },
  statusText: {
    fontSize: 11,
    fontWeight: "700",
  },
  statusTextTaken: {
    color: "#059669",
  },
  statusTextDue: {
    color: "#D97706",
  },
  statusTextSkipped: {
    color: "#64748B",
  },
  statusTextSnoozed: {
    color: "#D97706",
  },
  medicationName: {
    fontSize: 16,
    fontWeight: "700",
    color: "#0F172A",
  },
  instructions: {
    fontSize: 13,
    color: "#64748B",
    marginTop: 4,
    lineHeight: 18,
  },
  metaRow: {
    marginTop: spacing.xs + 2,
    flexDirection: "row",
    alignItems: "center",
  },
  prescriberTag: {
    fontSize: 12,
    color: "#64748B",
    fontStyle: "italic",
  },
  actionContainer: {
    marginTop: spacing.sm + 2,
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: "#EEF2F6",
  },
  takenButton: {
    flexDirection: "row",
    backgroundColor: "#0D9488",
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
    color: "#FFFFFF",
    fontSize: 14,
    fontWeight: "700",
  },
  secondaryActionsRow: {
    flexDirection: "row",
    gap: spacing.xs,
    marginTop: spacing.xs,
  },
  secondaryActionBtn: {
    flex: 1,
    flexDirection: "row",
    paddingVertical: 9,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    backgroundColor: "#F8FAFC",
    minHeight: 38,
  },
  secondaryActionText: {
    fontSize: 12,
    fontWeight: "600",
    color: "#475569",
  },
});
