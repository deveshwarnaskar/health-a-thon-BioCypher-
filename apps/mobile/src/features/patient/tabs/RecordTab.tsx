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

export type RecordOptionKey =
  | "glucose"
  | "meal"
  | "medication"
  | "activity"
  | "weight"
  | "blood_pressure"
  | "symptoms"
  | "sleep"
  | "documents"
  | "task";

export type RecordTabProps = {
  onSelectOption: (option: RecordOptionKey) => void;
  onOpenAssist?: () => void;
};

type RecordOption = {
  key: RecordOptionKey;
  title: string;
  subtitle: string;
  badge?: string;
  iconName: keyof typeof Ionicons.glyphMap;
  iconColor: string;
  iconBg: string;
};

const PRIMARY_OPTIONS: RecordOption[] = [
  {
    key: "glucose",
    title: "Blood Glucose",
    subtitle: "Log fasting, post-meal, or bedtime capillary glucose reading (mg/dL)",
    badge: "PRIMARY METRIC",
    iconName: "water-outline",
    iconColor: "#DC2626",
    iconBg: "rgba(239, 68, 68, 0.12)",
  },
  {
    key: "meal",
    title: "Meal & Nutrition",
    subtitle: "Record meals and Indian recipes with standard Katori portion sizing",
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
    key: "activity",
    title: "Physical Activity",
    subtitle: "Log walking, running, yoga, cycling, or home exercise",
    badge: "LIFESTYLE",
    iconName: "walk-outline",
    iconColor: "#059669",
    iconBg: "rgba(16, 185, 129, 0.12)",
  },
];

const SECONDARY_OPTIONS: RecordOption[] = [
  {
    key: "weight",
    title: "Body Weight",
    subtitle: "Track weight in kg or lbs with optional context tagging",
    badge: "VITAL",
    iconName: "scale-outline",
    iconColor: "#0284C7",
    iconBg: "rgba(2, 132, 199, 0.12)",
  },
  {
    key: "blood_pressure",
    title: "Blood Pressure & Pulse",
    subtitle: "Log systolic, diastolic pressure (mmHg) and resting pulse (BPM)",
    badge: "VITAL",
    iconName: "heart-outline",
    iconColor: "#E11D48",
    iconBg: "rgba(225, 29, 72, 0.12)",
  },
  {
    key: "symptoms",
    title: "Symptoms & Events",
    subtitle: "Observed unusual sensations like shakiness, sweating, or fatigue",
    badge: "OBSERVATION",
    iconName: "alert-circle-outline",
    iconColor: "#D97706",
    iconBg: "rgba(217, 119, 6, 0.12)",
  },
  {
    key: "sleep",
    title: "Sleep & Rest",
    subtitle: "Record sleep duration and subjective quality of rest",
    badge: "RECOVERY",
    iconName: "moon-outline",
    iconColor: "#7C3AED",
    iconBg: "rgba(124, 58, 237, 0.12)",
  },
  {
    key: "documents",
    title: "Documents & Lab Reports",
    subtitle: "Review or upload clinical lab test sheets and doctor prescriptions",
    badge: "CLINICAL",
    iconName: "document-text-outline",
    iconColor: "#0D5C75",
    iconBg: "rgba(13, 92, 117, 0.12)",
  },
  {
    key: "task",
    title: "Care Task",
    subtitle: "Review and complete scheduled care plan tasks from your clinic",
    badge: "CARE PLAN",
    iconName: "checkbox-outline",
    iconColor: "#4B5563",
    iconBg: "rgba(75, 85, 99, 0.12)",
  },
];

export function RecordTab({ onSelectOption, onOpenAssist }: RecordTabProps) {
  const renderCard = (option: RecordOption) => (
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
  );

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

        {/* Section 1: Primary Care Logging */}
        <View style={styles.sectionHeaderRow}>
          <Text style={styles.sectionTitle} allowFontScaling>
            Primary Daily Logging
          </Text>
          <Text style={styles.sectionCaption} allowFontScaling>
            Key metabolic signals
          </Text>
        </View>
        <View style={styles.optionsList}>
          {PRIMARY_OPTIONS.map(renderCard)}
        </View>

        {/* Section 2: Contextual Health Observations */}
        <View style={[styles.sectionHeaderRow, { marginTop: spacing.sm }]}>
          <Text style={styles.sectionTitle} allowFontScaling>
            Contextual Health Observations
          </Text>
          <Text style={styles.sectionCaption} allowFontScaling>
            Vitals, symptoms, & lifestyle
          </Text>
        </View>
        <View style={styles.optionsList}>
          {SECONDARY_OPTIONS.map(renderCard)}
        </View>

        <View style={styles.safetyBox} accessibilityRole="summary">
          <View style={styles.safetyHeaderRow}>
            <Ionicons name="shield-checkmark" size={18} color="#059669" />
            <Text style={styles.safetyTitle} allowFontScaling>
              Clinical Data Integrity
            </Text>
          </View>
          <Text style={styles.safetyText} allowFontScaling>
            Your logs are securely reviewed by your verified clinician to tailor your precision care plan.
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
    paddingBottom: 110,
  },
  introBox: {
    backgroundColor: "#F0FDFA",
    borderRadius: 20,
    borderWidth: 1,
    borderColor: "#CCFBF1",
    padding: spacing.md,
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 12,
    elevation: 2,
  },
  kicker: {
    fontSize: 10,
    fontWeight: "700",
    color: "#0D9488",
    letterSpacing: 1.2,
    marginBottom: 4,
  },
  headline: {
    fontSize: 20,
    lineHeight: 26,
    fontWeight: "700",
    color: "#0F172A",
    letterSpacing: -0.2,
  },
  bodyText: {
    fontSize: 13,
    color: "#64748B",
    marginTop: 4,
    lineHeight: 18,
  },
  sectionHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "baseline",
    marginTop: spacing.xs,
    marginBottom: 2,
    paddingHorizontal: 2,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: "700",
    color: "#0F172A",
  },
  sectionCaption: {
    fontSize: 12,
    color: "#94A3B8",
  },
  optionsList: {
    gap: 10,
  },
  optionCard: {
    backgroundColor: colors.surface,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    padding: spacing.md,
    flexDirection: "row",
    alignItems: "center",
    minHeight: 68,
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 10,
    elevation: 2,
  },
  iconCircle: {
    width: 44,
    height: 44,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacing.md,
  },
  optionTextColumn: {
    flex: 1,
  },
  badgeRow: {
    flexDirection: "row",
    marginBottom: 3,
  },
  badge: {
    backgroundColor: "#F1F5F9",
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: radii.pill,
  },
  badgeText: {
    fontSize: 9,
    fontWeight: "700",
    color: "#475569",
    letterSpacing: 0.6,
  },
  optionTitle: {
    fontSize: 15,
    fontWeight: "700",
    color: "#0F172A",
  },
  optionSubtitle: {
    fontSize: 12,
    color: "#64748B",
    marginTop: 2,
    lineHeight: 17,
  },
  arrowContainer: {
    minWidth: 24,
    alignItems: "center",
    justifyContent: "center",
    marginLeft: spacing.xs,
  },
  safetyBox: {
    backgroundColor: "#ECFDF5",
    borderRadius: 18,
    borderWidth: 1,
    borderColor: "#A7F3D0",
    padding: spacing.md,
    marginTop: spacing.xs,
    gap: 4,
  },
  safetyHeaderRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  safetyTitle: {
    fontSize: 13,
    fontWeight: "700",
    color: "#065F46",
  },
  safetyText: {
    fontSize: 12,
    color: "#047857",
    lineHeight: 18,
  },
});
