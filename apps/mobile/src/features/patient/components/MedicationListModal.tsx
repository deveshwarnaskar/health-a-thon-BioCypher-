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
        {/* Header */}
        <View style={styles.header}>
          <View>
            <View style={styles.kickerRow}>
              <View style={styles.kickerDot} />
              <Text style={styles.kicker} allowFontScaling>
                CLINICAL PHARMACOTHERAPY
              </Text>
            </View>
            <Text style={styles.title} allowFontScaling>
              Prescribed Medications
            </Text>
          </View>
          <TouchableOpacity
            style={styles.closeButton}
            onPress={onClose}
            accessibilityRole="button"
            accessibilityLabel="Close medications modal"
            activeOpacity={0.7}
          >
            <Ionicons name="close" size={20} color="#0F172A" />
          </TouchableOpacity>
        </View>

        <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
          {/* Disclaimer Box */}
          <View style={styles.disclaimerBox} accessibilityRole="summary">
            <View style={styles.disclaimerIconBox}>
              <Ionicons name="shield-checkmark" size={18} color="#0D9488" />
            </View>
            <View style={styles.disclaimerTextCol}>
              <Text style={styles.disclaimerTitle} allowFontScaling>
                Clinician-Authored Treatment
              </Text>
              <Text style={styles.disclaimerText} allowFontScaling>
                Medications are prescribed and titrated by your doctor. Contact your clinic if you need dosage adjustments or prescription renewals.
              </Text>
            </View>
          </View>

          {feedbackMessage && (
            <View style={styles.feedbackBanner}>
              <Ionicons name="checkmark-circle" size={16} color="#059669" style={{ marginRight: 6 }} />
              <Text style={styles.feedbackBannerText} allowFontScaling>
                {feedbackMessage}
              </Text>
            </View>
          )}

          {plans.length === 0 ? (
            <View style={styles.emptyContainer}>
              <View style={styles.emptyIconCircle}>
                <Ionicons name="medkit-outline" size={34} color="#0D9488" />
              </View>
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
    paddingTop: spacing.sm,
    paddingBottom: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: "#E2E8F0",
    backgroundColor: colors.surface,
  },
  kickerRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 2,
  },
  kickerDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: "#0D9488",
    marginRight: 6,
  },
  kicker: {
    fontSize: 10,
    color: "#64748B",
    fontWeight: "700",
    letterSpacing: 1.1,
  },
  title: {
    fontSize: 20,
    fontWeight: "800",
    color: "#0F172A",
    letterSpacing: -0.3,
  },
  closeButton: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: "#F8FAFC",
    borderWidth: 1,
    borderColor: "#E2E8F0",
    alignItems: "center",
    justifyContent: "center",
  },
  content: {
    padding: spacing.md,
    gap: spacing.sm + 2,
  },
  disclaimerBox: {
    flexDirection: "row",
    backgroundColor: "#F0FDFA",
    borderRadius: 18,
    borderWidth: 1,
    borderColor: "#CCFBF1",
    padding: spacing.md,
    gap: spacing.sm,
    alignItems: "flex-start",
  },
  disclaimerIconBox: {
    width: 32,
    height: 32,
    borderRadius: 10,
    backgroundColor: "#CCFBF1",
    alignItems: "center",
    justifyContent: "center",
  },
  disclaimerTextCol: {
    flex: 1,
  },
  disclaimerTitle: {
    fontSize: 13,
    fontWeight: "700",
    color: "#0F766E",
    marginBottom: 2,
  },
  disclaimerText: {
    fontSize: 11,
    color: "#0D9488",
    lineHeight: 16,
  },
  emptyContainer: {
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: spacing.xxl,
  },
  emptyIconCircle: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: "#F0FDFA",
    borderWidth: 1,
    borderColor: "#CCFBF1",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.md,
  },
  emptyTitle: {
    fontSize: typography.fontSize.headline,
    fontWeight: "800",
    color: colors.textPrimary,
  },
  emptySubtitle: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textSecondary,
    marginTop: spacing.xs,
    textAlign: "center",
    maxWidth: 280,
    lineHeight: 18,
  },
  feedbackBanner: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#ECFDF5",
    borderWidth: 1,
    borderColor: "#A7F3D0",
    padding: spacing.sm + 2,
    borderRadius: 14,
  },
  feedbackBannerText: {
    fontSize: 13,
    color: "#059669",
    fontWeight: "600",
  },
});
