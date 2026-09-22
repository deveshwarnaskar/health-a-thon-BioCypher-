import React, { useState } from "react";
import {
  Modal,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { colors, radii, spacing, touchTarget, typography } from "../../../theming/tokens";
import {
  PatientMedicationCard,
  type MedicationAdherenceAction,
} from "../components/PatientMedicationCard";
import { usePatientMedications, useAdministerMedication } from "../api";
export type MedicationListModalProps = {
  visible: boolean;
  onClose: () => void;
  patientId: string | null;
};

export function MedicationListModal({
  visible,
  onClose,
  patientId,
}: MedicationListModalProps) {
  const { data: plans = [] } = usePatientMedications(patientId);
  const administerMutation = useAdministerMedication();
  const [adherenceMap, setAdherenceMap] = useState<Record<string, "TAKEN" | "SKIPPED" | "SNOOZED">>({});
  const [feedbackMessage, setFeedbackMessage] = useState<string | null>(null);

  const handleMarkTaken = (
    planId: string,
    action: MedicationAdherenceAction = "NOW",
    administeredAt?: string
  ) => {
    if (action === "SKIPPED") {
      setAdherenceMap((prev) => ({ ...prev, [planId]: "SKIPPED" }));
      setFeedbackMessage("Dose marked as skipped.");
      setTimeout(() => setFeedbackMessage(null), 3000);
      return;
    }
    if (action === "SNOOZE") {
      setAdherenceMap((prev) => ({ ...prev, [planId]: "SNOOZED" }));
      setFeedbackMessage("Reminder snoozed for 15 minutes.");
      setTimeout(() => setFeedbackMessage(null), 3000);
      return;
    }

    const resolvedTime = administeredAt || new Date().toISOString();
    administerMutation.mutate(
      { medicationPlanId: planId, administeredAt: resolvedTime },
      {
        onSuccess: () => {
          setAdherenceMap((prev) => ({ ...prev, [planId]: "TAKEN" }));
          setFeedbackMessage("Dose recorded successfully.");
          setTimeout(() => setFeedbackMessage(null), 3000);
        },
      }
    );
  };

  return (
    <Modal
      visible={visible}
      animationType="slide"
      presentationStyle="pageSheet"
      onRequestClose={onClose}
    >
      <SafeAreaView style={styles.container}>
        <View style={styles.header}>
          <View>
            <Text style={styles.title} allowFontScaling>
              Prescribed Medications
            </Text>
            <Text style={styles.subtitle} allowFontScaling>
              Clinician-authored treatment plans
            </Text>
          </View>
          <TouchableOpacity
            style={styles.closeButton}
            onPress={onClose}
            accessibilityRole="button"
            accessibilityLabel="Close medications modal"
          >
            <Ionicons name="close" size={22} color={colors.textPrimary} />
          </TouchableOpacity>
        </View>

        <ScrollView contentContainerStyle={styles.content}>
          <View style={styles.disclaimerBox} accessibilityRole="summary">
            <Text style={styles.disclaimerTitle} allowFontScaling>
              Clinician-Authored Treatment
            </Text>
            <Text style={styles.disclaimerText} allowFontScaling>
              Medications are prescribed and titrated by your doctor. Contact your clinic if you need dosage or prescription changes.
            </Text>
          </View>

          {feedbackMessage && (
            <View style={styles.feedbackBanner}>
              <Text style={styles.feedbackBannerText} allowFontScaling>
                {feedbackMessage}
              </Text>
            </View>
          )}

          {plans.length === 0 ? (
            <View style={styles.emptyContainer}>
              <Text style={styles.emptyIcon} allowFontScaling>
                💊
              </Text>
              <Text style={styles.emptyTitle} allowFontScaling>
                No active medication plans
              </Text>
              <Text style={styles.emptySubtitle} allowFontScaling>
                When your clinician prescribes medications, they will appear here with instructions and schedules.
              </Text>
            </View>
          ) : (
            plans.map((plan) => (
              <PatientMedicationCard
                key={plan.medication_plan_id}
                plan={plan}
                adherenceStatus={adherenceMap[plan.medication_plan_id]}
                onMarkTaken={handleMarkTaken}
                isMarking={administerMutation.isPending}
              />
            ))
          )}
        </ScrollView>
      </SafeAreaView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    backgroundColor: colors.surface,
  },
  title: {
    fontSize: typography.fontSize.title,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
  },
  subtitle: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
  },
  closeButton: {
    minWidth: touchTarget.min,
    minHeight: touchTarget.min,
    alignItems: "center",
    justifyContent: "center",
  },
  closeText: {
    fontSize: 18,
    color: colors.textSecondary,
    fontWeight: "bold",
  },
  content: {
    padding: spacing.md,
  },
  disclaimerBox: {
    backgroundColor: "#FDF9F5",
    borderRadius: radii.md,
    borderLeftWidth: 3,
    borderLeftColor: colors.assistive,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  disclaimerTitle: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.weight.bold,
    color: colors.assistive,
    marginBottom: 2,
  },
  disclaimerText: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    lineHeight: 18,
  },
  emptyContainer: {
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: spacing.xxl,
  },
  emptyIcon: {
    fontSize: 48,
    marginBottom: spacing.md,
  },
  emptyTitle: {
    fontSize: typography.fontSize.headline,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
  },
  emptySubtitle: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textSecondary,
    marginTop: spacing.xs,
    textAlign: "center",
    maxWidth: 280,
  },
  feedbackBanner: {
    backgroundColor: colors.tileGreen,
    padding: spacing.sm,
    borderRadius: radii.md,
    marginBottom: spacing.md,
  },
  feedbackBannerText: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.leafGreen,
    fontWeight: typography.weight.medium,
  },
});
