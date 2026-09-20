import React from "react";
import {
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { colors, radii, spacing, typography } from "../../../theming/tokens";
import { PatientScreenHeader } from "../components/PatientScreenHeader";

export type RecordTabProps = {
  onSelectOption: (option: "glucose" | "meal" | "medication" | "task") => void;
  onOpenAssist?: () => void;
};

type RecordOption = {
  key: "glucose" | "meal" | "medication" | "task";
  title: string;
  subtitle: string;
  badge?: string;
  icon: string;
};

const RECORD_OPTIONS: RecordOption[] = [
  {
    key: "glucose",
    title: "Blood Glucose",
    subtitle: "Log your fasting, post-meal, or random glucose reading (mg/dL)",
    badge: "DAILY METRIC",
    icon: "🩸",
  },
  {
    key: "meal",
    title: "Meal & Nutrition",
    subtitle: "Record breakfast, lunch, snack, or dinner with Katori portion sizing",
    badge: "NUTRITION",
    icon: "🍲",
  },
  {
    key: "medication",
    title: "Medication Dose",
    subtitle: "Confirm you took your prescribed clinician medication",
    badge: "ADHERENCE",
    icon: "💊",
  },
  {
    key: "task",
    title: "Care Task",
    subtitle: "Review and complete scheduled care plan tasks for your clinic",
    badge: "CARE PLAN",
    icon: "📋",
  },
];

export function RecordTab({ onSelectOption, onOpenAssist }: RecordTabProps) {
  return (
    <View style={styles.container}>
      <PatientScreenHeader
        title="Record Health Data"
        subtitle="Select what you'd like to log today"
        onPressAssist={onOpenAssist}
      />

      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.introBox}>
          <Text style={styles.kicker} allowFontScaling>
            CAPTURE & TRACK
          </Text>
          <Text style={styles.headline} allowFontScaling>
            What would you like to record?
          </Text>
          <Text style={styles.bodyText} allowFontScaling>
            Entries are saved securely on this device and synchronized with your clinical care team.
          </Text>
        </View>

        <View style={styles.optionsList}>
          {RECORD_OPTIONS.map((option) => (
            <TouchableOpacity
              key={option.key}
              style={styles.optionCard}
              onPress={() => onSelectOption(option.key)}
              activeOpacity={0.7}
              accessibilityRole="button"
              accessibilityLabel={`${option.title}: ${option.subtitle}`}
              accessibilityHint={`Opens the ${option.title} recording screen`}
            >
              <View style={styles.iconCircle}>
                <Text style={styles.iconText} allowFontScaling>
                  {option.icon}
                </Text>
              </View>

              <View style={styles.optionTextColumn}>
                <View style={styles.badgeRow}>
                  <View style={styles.badge}>
                    <Text style={styles.badgeText} allowFontScaling>
                      {option.badge}
                    </Text>
                  </View>
                </View>
                <Text style={styles.optionTitle} allowFontScaling>
                  {option.title}
                </Text>
                <Text style={styles.optionSubtitle} allowFontScaling>
                  {option.subtitle}
                </Text>
              </View>

              <View style={styles.arrowContainer}>
                <Text style={styles.arrowText} allowFontScaling>
                  →
                </Text>
              </View>
            </TouchableOpacity>
          ))}
        </View>

        <View style={styles.safetyBox} accessibilityRole="summary">
          <Text style={styles.safetyTitle} allowFontScaling>
            Clinical Data Integrity
          </Text>
          <Text style={styles.safetyText} allowFontScaling>
            Your logs are reviewed by your verified clinician to tailor your precision care plan.
          </Text>
        </View>
      </ScrollView>
    </View>
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
  },
  introBox: {
    paddingVertical: spacing.xs,
  },
  kicker: {
    fontSize: 11,
    fontWeight: typography.weight.bold,
    color: colors.primary,
    letterSpacing: 1.2,
    marginBottom: 4,
  },
  headline: {
    fontSize: typography.fontSize.headline,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
  },
  bodyText: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textSecondary,
    marginTop: 4,
    lineHeight: typography.lineHeight.bodySmall,
  },
  optionsList: {
    gap: spacing.sm,
  },
  optionCard: {
    backgroundColor: colors.surface,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    flexDirection: "row",
    alignItems: "center",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 3,
    elevation: 2,
  },
  iconCircle: {
    width: 48,
    height: 48,
    borderRadius: radii.md,
    backgroundColor: "#F0F7F9",
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacing.md,
  },
  iconText: {
    fontSize: 22,
  },
  optionTextColumn: {
    flex: 1,
  },
  badgeRow: {
    flexDirection: "row",
    marginBottom: 2,
  },
  badge: {
    backgroundColor: "#E8F4F8",
    paddingHorizontal: 6,
    paddingVertical: 1,
    borderRadius: radii.sm,
  },
  badgeText: {
    fontSize: 9,
    fontWeight: typography.weight.bold,
    color: colors.primary,
    letterSpacing: 0.6,
  },
  optionTitle: {
    fontSize: typography.fontSize.body,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
  },
  optionSubtitle: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    marginTop: 2,
    lineHeight: typography.lineHeight.caption,
  },
  arrowContainer: {
    minWidth: 28,
    alignItems: "center",
    justifyContent: "center",
    marginLeft: spacing.xs,
  },
  arrowText: {
    fontSize: 20,
    color: colors.textSecondary,
    fontWeight: "600",
  },
  safetyBox: {
    backgroundColor: "#F8FAF9",
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: "#D5E8D4",
    padding: spacing.md,
    marginTop: spacing.xs,
  },
  safetyTitle: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.weight.bold,
    color: colors.leafGreen,
    marginBottom: 2,
  },
  safetyText: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    lineHeight: 18,
  },
});
