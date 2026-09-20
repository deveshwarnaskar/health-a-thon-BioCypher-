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
import { colors, radii, spacing, touchTarget, typography } from "../../../theming/tokens";
import { useConnectivity } from "../../../connectivity/useConnectivity";

export type ThaliAssistModalProps = {
  visible: boolean;
  onClose: () => void;
  onNavigateToRecords?: () => void;
  onNavigateToMeal?: () => void;
};

type AssistTopic = "today" | "meal" | "appointment" | null;

export function ThaliAssistModal({
  visible,
  onClose,
  onNavigateToRecords,
  onNavigateToMeal,
}: ThaliAssistModalProps) {
  const { isOffline } = useConnectivity();
  const [selectedTopic, setSelectedTopic] = useState<AssistTopic>(null);

  const handleSelectTopic = (topic: AssistTopic) => {
    setSelectedTopic(topic);
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
          <View style={styles.headerTitleRow}>
            <Text style={styles.assistIcon} allowFontScaling>
              ✦
            </Text>
            <View>
              <Text style={styles.title} allowFontScaling>
                THALI Assist
              </Text>
              <Text style={styles.subtitle} allowFontScaling>
                Care understanding guide
              </Text>
            </View>
          </View>
          <TouchableOpacity
            style={styles.closeButton}
            onPress={onClose}
            accessibilityRole="button"
            accessibilityLabel="Close THALI Assist"
          >
            <Text style={styles.closeText} allowFontScaling>
              ✕
            </Text>
          </TouchableOpacity>
        </View>

        {isOffline ? (
          <View style={styles.offlineNotice} accessibilityRole="alert">
            <Text style={styles.offlineIcon} allowFontScaling>
              📡
            </Text>
            <Text style={styles.offlineText} allowFontScaling>
              Assist features require an active connection to access your verified clinic records.
            </Text>
          </View>
        ) : null}

        <ScrollView contentContainerStyle={styles.content}>
          <View style={styles.disclaimerBox} accessibilityRole="summary">
            <Text style={styles.disclaimerTitle} allowFontScaling>
              Patient-Safe Care Guide
            </Text>
            <Text style={styles.disclaimerText} allowFontScaling>
              THALI Assist helps you review and organize your personal recordings. It does not provide medical diagnoses, prescribe treatments, or alter your clinician-authored plan.
            </Text>
          </View>

          {selectedTopic === null ? (
            <View style={styles.promptSection}>
              <Text style={styles.promptHeader} allowFontScaling>
                What would you like help with?
              </Text>

              <TouchableOpacity
                style={styles.optionCard}
                onPress={() => handleSelectTopic("today")}
                activeOpacity={0.7}
                accessibilityRole="button"
                accessibilityLabel="Understand today's records"
              >
                <Text style={styles.optionIcon} allowFontScaling>
                  📊
                </Text>
                <View style={styles.optionTextColumn}>
                  <Text style={styles.optionTitle} allowFontScaling>
                    {"Understand today's records"}
                  </Text>
                  <Text style={styles.optionSubtitle} allowFontScaling>
                    Review glucose patterns and meals you logged today.
                  </Text>
                </View>
                <Text style={styles.chevron} allowFontScaling>
                  →
                </Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.optionCard}
                onPress={() => handleSelectTopic("meal")}
                activeOpacity={0.7}
                accessibilityRole="button"
                accessibilityLabel="Understand a meal entry"
              >
                <Text style={styles.optionIcon} allowFontScaling>
                  🍲
                </Text>
                <View style={styles.optionTextColumn}>
                  <Text style={styles.optionTitle} allowFontScaling>
                    Understand a meal entry
                  </Text>
                  <Text style={styles.optionSubtitle} allowFontScaling>
                    How your meal portions connect to your care plan.
                  </Text>
                </View>
                <Text style={styles.chevron} allowFontScaling>
                  →
                </Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.optionCard}
                onPress={() => handleSelectTopic("appointment")}
                activeOpacity={0.7}
                accessibilityRole="button"
                accessibilityLabel="Prepare for an appointment"
              >
                <Text style={styles.optionIcon} allowFontScaling>
                  📋
                </Text>
                <View style={styles.optionTextColumn}>
                  <Text style={styles.optionTitle} allowFontScaling>
                    Prepare for an appointment
                  </Text>
                  <Text style={styles.optionSubtitle} allowFontScaling>
                    Checklist of summaries and questions for your doctor.
                  </Text>
                </View>
                <Text style={styles.chevron} allowFontScaling>
                  →
                </Text>
              </TouchableOpacity>
            </View>
          ) : null}

          {selectedTopic === "today" ? (
            <View style={styles.topicDetail}>
              <View style={styles.provenanceTag}>
                <Text style={styles.provenanceText} allowFontScaling>
                  PATIENT DATA REVIEW
                </Text>
              </View>
              <Text style={styles.topicTitle} allowFontScaling>
                {"Today's Care Insights"}
              </Text>
              <Text style={styles.topicBody} allowFontScaling>
                • Your recorded glucose readings are saved and available for clinician review.
                {"\n\n"}
                • Regular logging around meals helps your care team understand how different foods influence your day.
                {"\n\n"}
                • All readings are cryptographically stored and synchronized with your clinical facility.
              </Text>

              <TouchableOpacity
                style={styles.actionButton}
                onPress={() => {
                  onClose();
                  onNavigateToRecords?.();
                }}
                accessibilityRole="button"
                accessibilityLabel="View full timeline records"
              >
                <Text style={styles.actionButtonText} allowFontScaling>
                  Open Timeline History
                </Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.backLink}
                onPress={() => setSelectedTopic(null)}
                accessibilityRole="button"
                accessibilityLabel="Choose another question"
              >
                <Text style={styles.backLinkText} allowFontScaling>
                  ← Choose another topic
                </Text>
              </TouchableOpacity>
            </View>
          ) : null}

          {selectedTopic === "meal" ? (
            <View style={styles.topicDetail}>
              <View style={styles.provenanceTag}>
                <Text style={styles.provenanceText} allowFontScaling>
                  NUTRITION GUIDANCE
                </Text>
              </View>
              <Text style={styles.topicTitle} allowFontScaling>
                Understanding Meal Portions
              </Text>
              <Text style={styles.topicBody} allowFontScaling>
                • THALI uses standard Katori measures (Small 100ml, Medium 150ml, Large 200ml) to help keep portion logging consistent.
                {"\n\n"}
                • Consistent portions allow your dietitian and doctor to evaluate your nutritional balance accurately without confusing calculations.
              </Text>

              <TouchableOpacity
                style={styles.actionButton}
                onPress={() => {
                  onClose();
                  onNavigateToMeal?.();
                }}
                accessibilityRole="button"
                accessibilityLabel="Log a new meal"
              >
                <Text style={styles.actionButtonText} allowFontScaling>
                  Log a Meal
                </Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.backLink}
                onPress={() => setSelectedTopic(null)}
                accessibilityRole="button"
                accessibilityLabel="Choose another question"
              >
                <Text style={styles.backLinkText} allowFontScaling>
                  ← Choose another topic
                </Text>
              </TouchableOpacity>
            </View>
          ) : null}

          {selectedTopic === "appointment" ? (
            <View style={styles.topicDetail}>
              <View style={styles.provenanceTag}>
                <Text style={styles.provenanceText} allowFontScaling>
                  CLINIC PREPARATION
                </Text>
              </View>
              <Text style={styles.topicTitle} allowFontScaling>
                Preparing for Your Next Visit
              </Text>
              <Text style={styles.topicBody} allowFontScaling>
                • Ensure your latest glucose observations and medication marks are logged up to today.
                {"\n\n"}
                • In the &apos;You&apos; tab, you can view your verified Clinical Care Summaries (PDF).
                {"\n\n"}
                • Note any symptoms or side-effects to share directly with your clinician.
              </Text>

              <TouchableOpacity
                style={styles.backLink}
                onPress={() => setSelectedTopic(null)}
                accessibilityRole="button"
                accessibilityLabel="Choose another question"
              >
                <Text style={styles.backLinkText} allowFontScaling>
                  ← Choose another topic
                </Text>
              </TouchableOpacity>
            </View>
          ) : null}
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
  headerTitleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  assistIcon: {
    fontSize: 24,
    color: colors.primary,
    fontWeight: "bold",
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
  offlineNotice: {
    backgroundColor: colors.warning,
    flexDirection: "row",
    alignItems: "center",
    padding: spacing.sm,
    gap: spacing.xs,
  },
  offlineIcon: {
    fontSize: 16,
  },
  offlineText: {
    color: colors.textOnPrimary,
    fontSize: typography.fontSize.caption,
    fontWeight: typography.weight.medium,
    flex: 1,
  },
  disclaimerBox: {
    backgroundColor: "#F0F7F9",
    borderRadius: radii.md,
    borderLeftWidth: 3,
    borderLeftColor: colors.primary,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  disclaimerTitle: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.weight.bold,
    color: colors.primary,
    marginBottom: 2,
    letterSpacing: 0.5,
  },
  disclaimerText: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    lineHeight: 18,
  },
  promptSection: {
    gap: spacing.sm,
  },
  promptHeader: {
    fontSize: typography.fontSize.body,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
    marginBottom: spacing.xs,
  },
  optionCard: {
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  optionIcon: {
    fontSize: 22,
  },
  optionTextColumn: {
    flex: 1,
  },
  optionTitle: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
  },
  optionSubtitle: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    marginTop: 2,
  },
  chevron: {
    fontSize: 18,
    color: colors.textSecondary,
  },
  topicDetail: {
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    gap: spacing.md,
  },
  provenanceTag: {
    alignSelf: "flex-start",
    backgroundColor: "#E8F4F8",
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: radii.sm,
  },
  provenanceText: {
    fontSize: 10,
    fontWeight: typography.weight.bold,
    color: colors.primary,
    letterSpacing: 0.8,
  },
  topicTitle: {
    fontSize: typography.fontSize.headline,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
  },
  topicBody: {
    fontSize: typography.fontSize.body,
    color: colors.textPrimary,
    lineHeight: typography.lineHeight.body,
  },
  actionButton: {
    backgroundColor: colors.primary,
    borderRadius: radii.md,
    minHeight: touchTarget.min,
    alignItems: "center",
    justifyContent: "center",
  },
  actionButtonText: {
    color: colors.textOnPrimary,
    fontSize: typography.fontSize.bodySmall,
    fontWeight: typography.weight.semibold,
  },
  backLink: {
    alignItems: "center",
    justifyContent: "center",
    minHeight: touchTarget.min,
  },
  backLinkText: {
    color: colors.primary,
    fontSize: typography.fontSize.bodySmall,
    fontWeight: typography.weight.medium,
  },
});
