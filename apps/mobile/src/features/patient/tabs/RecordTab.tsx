import React from "react";
import {
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
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
  iconName: keyof typeof Ionicons.glyphMap;
  iconColor: string;
  iconBg: string;
};

const RECORD_OPTIONS: RecordOption[] = [
  {
    key: "glucose",
    title: "Blood Glucose",
    subtitle: "Log your fasting, post-meal, or random glucose reading (mg/dL)",
    badge: "DAILY METRIC",
    iconName: "water-outline",
    iconColor: "#DC2626",
    iconBg: "rgba(239, 68, 68, 0.12)",
  },
  {
    key: "meal",
    title: "Meal & Nutrition",
    subtitle: "Record breakfast, lunch, snack, or dinner with Katori portion sizing",
    badge: "NUTRITION",
    iconName: "restaurant-outline",
    iconColor: "#D97706",
    iconBg: "rgba(245, 158, 11, 0.12)",
  },
  {
    key: "medication",
    title: "Medication Dose",
    subtitle: "Confirm you took your prescribed clinician medication",
    badge: "ADHERENCE",
    iconName: "medkit-outline",
    iconColor: "#2563EB",
    iconBg: "rgba(59, 130, 246, 0.12)",
  },
  {
    key: "task",
    title: "Care Task",
    subtitle: "Review and complete scheduled care plan tasks for your clinic",
    badge: "CARE PLAN",
    iconName: "checkbox-outline",
    iconColor: "#059669",
    iconBg: "rgba(16, 185, 129, 0.12)",
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
              <View style={[styles.iconCircle, { backgroundColor: option.iconBg }]}>
                <Ionicons name={option.iconName} size={22} color={option.iconColor} />
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
                <Ionicons name="chevron-forward" size={18} color="#94A3B8" />
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
    paddingBottom: 100,
  },
  introBox: {
    backgroundColor: colors.tileAqua,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: "#FFFFFF",
    padding: spacing.md,
    shadowColor: colors.primaryInk,
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.07,
    shadowRadius: 16,
    elevation: 2,
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
    borderColor: "#FFFFFF",
    padding: spacing.md,
    flexDirection: "row",
    alignItems: "center",
    shadowColor: colors.primaryInk,
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.07,
    shadowRadius: 16,
    elevation: 3,
  },
  iconCircle: {
    width: 48,
    height: 48,
    borderRadius: radii.pill,
    backgroundColor: colors.tileAqua,
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
    backgroundColor: colors.tileAqua,
    paddingHorizontal: 6,
    paddingVertical: 1,
    borderRadius: radii.pill,
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
    backgroundColor: colors.tileGreen,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: "#FFFFFF",
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
