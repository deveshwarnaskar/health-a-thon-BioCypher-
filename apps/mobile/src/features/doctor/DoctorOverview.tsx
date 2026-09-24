import React from "react";
import { StyleSheet, Text, View, ScrollView, Pressable, useWindowDimensions } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Badge } from "../../components/primitives/Badge";
import { spacing, typography } from "../../theming/tokens";
import { doctorPalette, doctorRadii, doctorSoftShadow } from "./doctorDesign";
import type { PatientSummaryResponse } from "../../services/schemas/patients";
import type { DoctorDestinationKey } from "./DoctorSidebar";

export type DoctorOverviewProps = {
  patients: PatientSummaryResponse[];
  reviewCount: number;
  taskCount: number;
  onSelectPatient: (patient: PatientSummaryResponse) => void;
  onNavigate: (dest: DoctorDestinationKey) => void;
};

export function DoctorOverview({
  patients,
  reviewCount,
  taskCount,
  onSelectPatient,
  onNavigate,
}: DoctorOverviewProps) {
  const { width } = useWindowDimensions();
  const isCompact = width < 760;
  const activePatients = patients.filter((p) => p.active);
  const inactivePatients = patients.filter((p) => !p.active);
  const quickActions: {
    dest: DoctorDestinationKey;
    title: string;
    meta: string;
    icon: React.ComponentProps<typeof Ionicons>["name"];
    tone: "lime" | "blue" | "white";
  }[] = [
    {
      dest: "patients",
      title: "Patients",
      meta: `${patients.length} records`,
      icon: "people",
      tone: "lime",
    },
    {
      dest: "review",
      title: "AI Review",
      meta: `${reviewCount} pending`,
      icon: "sparkles",
      tone: "white",
    },
    {
      dest: "monitoring",
      title: "Monitoring",
      meta: `${activePatients.length} active`,
      icon: "analytics",
      tone: "white",
    },
    {
      dest: "reports",
      title: "Reports",
      meta: "Clinical PDFs",
      icon: "document-text",
      tone: "blue",
    },
  ];

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={[styles.heroSection, isCompact ? styles.heroSectionCompact : null]}>
        <View style={styles.heroCopy}>
          <Text style={styles.heroEyebrow}>Clinical Workspace</Text>
          <Text style={[styles.heading, isCompact ? styles.headingCompact : null]}>
            Your patient command center
          </Text>
          <Text style={styles.subheading}>
            Facility summary, priority reviews, and follow-up work for today&apos;s clinical rounds.
          </Text>
        </View>
        <View style={styles.heroBadge}>
          <Ionicons name="shield-checkmark" size={26} color={doctorPalette.primary} />
          <Text style={styles.heroBadgeValue}>{activePatients.length}</Text>
          <Text style={styles.heroBadgeLabel}>Active</Text>
        </View>
      </View>

      <View style={styles.quickGrid}>
        {quickActions.map((action) => {
          const tileStyle =
            action.tone === "lime"
              ? styles.quickTileLime
              : action.tone === "blue"
              ? styles.quickTileBlue
              : styles.quickTileWhite;
          const iconStyle =
            action.tone === "blue" ? styles.quickIconOnBlue : styles.quickIconDefault;
          const textStyle = action.tone === "blue" ? styles.quickTextOnBlue : null;
          return (
            <Pressable
              key={action.dest}
              style={[styles.quickTile, tileStyle]}
              onPress={() => onNavigate(action.dest)}
              accessibilityRole="button"
              accessibilityLabel={`Open ${action.title}`}
            >
              <View style={[styles.quickIcon, iconStyle]}>
                <Ionicons
                  name={action.icon}
                  size={22}
                  color={action.tone === "blue" ? doctorPalette.primary : doctorPalette.ink}
                />
              </View>
              <Text style={[styles.quickTitle, textStyle]} numberOfLines={1}>
                {action.title}
              </Text>
              <Text style={[styles.quickMeta, textStyle]} numberOfLines={1}>
                {action.meta}
              </Text>
            </Pressable>
          );
        })}
      </View>

      <View style={styles.metricGrid}>
        <Pressable
          style={[styles.metricCard, { borderLeftColor: doctorPalette.primary }]}
          onPress={() => onNavigate("patients")}
          accessibilityRole="button"
          accessibilityLabel="Open patient directory"
        >
          <Text style={styles.metricNumber}>{patients.length}</Text>
          <Text style={styles.metricTitle}>Total Patients</Text>
          <Text style={styles.metricSubtitle}>{activePatients.length} Active · {inactivePatients.length} Inactive</Text>
        </Pressable>

        <Pressable
          style={[
            styles.metricCard,
            { borderLeftColor: reviewCount > 0 ? "#F5A524" : "#47B741" },
          ]}
          onPress={() => onNavigate("review")}
          accessibilityRole="button"
          accessibilityLabel="Open AI review queue"
        >
          <Text style={[styles.metricNumber, reviewCount > 0 ? { color: "#F5A524" } : null]}>
            {reviewCount}
          </Text>
          <Text style={styles.metricTitle}>Pending AI Reviews</Text>
          <Text style={styles.metricSubtitle}>
            {reviewCount > 0 ? "Requires clinician sign-off" : "All artifacts reviewed"}
          </Text>
        </Pressable>

        <Pressable
          style={[styles.metricCard, { borderLeftColor: doctorPalette.primary }]}
          onPress={() => onNavigate("tasks")}
          accessibilityRole="button"
          accessibilityLabel="Open care tasks"
        >
          <Text style={styles.metricNumber}>{taskCount}</Text>
          <Text style={styles.metricTitle}>Care Tasks</Text>
          <Text style={styles.metricSubtitle}>Facility care team workflow</Text>
        </Pressable>

        <Pressable
          style={[styles.metricCard, { borderLeftColor: "#47B741" }]}
          onPress={() => onNavigate("monitoring")}
          accessibilityRole="button"
          accessibilityLabel="Open monitoring"
        >
          <Text style={styles.metricNumber}>100%</Text>
          <Text style={styles.metricTitle}>Data Provenance</Text>
          <Text style={styles.metricSubtitle}>Deterministic calculations verified</Text>
        </Pressable>
      </View>

      {reviewCount > 0 ? (
        <View style={[styles.alertCard, isCompact ? styles.alertCardCompact : null]}>
          <View style={styles.alertHeader}>
            <View style={styles.alertIcon}>
              <Ionicons name="flash" size={20} color="#92400E" />
            </View>
            <View style={styles.alertInfo}>
              <Text style={styles.alertTitle}>AI Review Queue Action Required</Text>
              <Text style={styles.alertText}>
                {reviewCount} pending AI-generated clinical artifacts await your review, edit, or approval.
              </Text>
            </View>
          </View>
          <Pressable style={styles.alertButton} onPress={() => onNavigate("review")}>
            <Text style={styles.alertButtonText}>Open Review Queue</Text>
          </Pressable>
        </View>
      ) : null}

      <View style={styles.section}>
        <View style={styles.sectionHeaderRow}>
          <Text style={styles.sectionTitle}>Facility Cohort Quick Access</Text>
          <Pressable onPress={() => onNavigate("patients")}>
            <Text style={styles.viewAllText}>View All ({patients.length})</Text>
          </Pressable>
        </View>

        <View style={styles.patientList}>
          {patients.slice(0, 6).map((patient) => (
            <Pressable
              key={patient.patient_id}
              style={styles.patientRow}
              onPress={() => onSelectPatient(patient)}
            >
              <View style={styles.patientRowLeft}>
                <View style={styles.avatarPill}>
                  <Text style={styles.avatarInitial}>{patient.name.charAt(0)}</Text>
                </View>
                <View style={styles.patientIdentity}>
                  <Text style={styles.patientName} numberOfLines={1}>{patient.name}</Text>
                  <Text style={styles.patientMeta}>UHID: {patient.uh_id}</Text>
                </View>
              </View>
              <View style={styles.patientRowRight}>
                <Badge
                  label={patient.active ? "Active" : "Inactive"}
                  tone={patient.active ? "success" : "neutral"}
                />
                <Text style={styles.openPatientAction}>Open Workspace</Text>
              </View>
            </Pressable>
          ))}
        </View>
      </View>

      <View style={styles.referenceCard}>
        <Text style={styles.referenceTitle}>Standards & Clinical Guidelines</Text>
        <Text style={styles.referenceText}>
          Deterministic metrics follow ADA / EASD Consensus (2019) and ICMR-NIN nutritional taxonomy.
          All automated alerts and AI suggestions are assistive; definitive clinical decisions,
          medication adjustments, and care plan modifications require licensed clinician authorization.
        </Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: doctorPalette.surfaceSoft,
  },
  content: {
    padding: spacing.lg,
    gap: spacing.lg,
    paddingBottom: spacing.xxl,
  },
  heroSection: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: spacing.md,
    backgroundColor: doctorPalette.surfaceBlue,
    borderRadius: doctorRadii.xl,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.9)",
    overflow: "hidden",
  },
  heroSectionCompact: {
    flexDirection: "column",
    alignItems: "stretch",
    padding: spacing.md,
  },
  heroCopy: {
    flex: 1,
    minWidth: 0,
    gap: 6,
  },
  heroEyebrow: {
    fontSize: typography.fontSize.caption,
    fontWeight: "800",
    color: doctorPalette.primary,
  },
  heroBadge: {
    width: 116,
    minHeight: 116,
    borderRadius: doctorRadii.xl,
    backgroundColor: doctorPalette.surface,
    alignItems: "center",
    justifyContent: "center",
    gap: 2,
    ...doctorSoftShadow,
  },
  heroBadgeValue: {
    fontSize: typography.fontSize.display,
    lineHeight: typography.lineHeight.display,
    fontWeight: "900",
    color: doctorPalette.ink,
  },
  heroBadgeLabel: {
    fontSize: typography.fontSize.caption,
    fontWeight: "800",
    color: doctorPalette.muted,
  },
  heading: {
    fontSize: 28,
    lineHeight: 34,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  headingCompact: {
    fontSize: 26,
    lineHeight: 31,
  },
  subheading: {
    fontSize: typography.fontSize.bodySmall,
    color: doctorPalette.muted,
    fontWeight: "600",
  },
  quickGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  quickTile: {
    flex: 1,
    minWidth: 142,
    minHeight: 128,
    borderRadius: doctorRadii.lg,
    padding: spacing.md,
    justifyContent: "space-between",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.84)",
    ...doctorSoftShadow,
  },
  quickTileLime: {
    backgroundColor: doctorPalette.surfaceLime,
  },
  quickTileBlue: {
    backgroundColor: doctorPalette.primary,
  },
  quickTileWhite: {
    backgroundColor: doctorPalette.surface,
  },
  quickIcon: {
    width: 46,
    height: 46,
    borderRadius: 23,
    alignItems: "center",
    justifyContent: "center",
  },
  quickIconDefault: {
    backgroundColor: "rgba(255,255,255,0.72)",
  },
  quickIconOnBlue: {
    backgroundColor: doctorPalette.surface,
  },
  quickTitle: {
    fontSize: typography.fontSize.body,
    fontWeight: "900",
    color: doctorPalette.ink,
  },
  quickMeta: {
    fontSize: typography.fontSize.caption,
    fontWeight: "700",
    color: doctorPalette.muted,
  },
  quickTextOnBlue: {
    color: doctorPalette.surface,
  },
  metricGrid: {
    flexDirection: "row",
    gap: spacing.md,
    flexWrap: "wrap",
  },
  metricCard: {
    flex: 1,
    minWidth: 200,
    backgroundColor: doctorPalette.surface,
    padding: spacing.md,
    borderRadius: doctorRadii.lg,
    borderWidth: 1,
    borderColor: doctorPalette.border,
    gap: 6,
    borderLeftWidth: 4,
    ...doctorSoftShadow,
  },
  metricNumber: {
    fontSize: typography.fontSize.display,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  metricTitle: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  metricSubtitle: {
    fontSize: typography.fontSize.caption,
    color: doctorPalette.muted,
  },
  alertCard: {
    backgroundColor: doctorPalette.warm,
    borderColor: "rgba(255,255,255,0.9)",
    borderWidth: 1,
    borderRadius: doctorRadii.lg,
    padding: spacing.md,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.md,
    flexWrap: "wrap",
    ...doctorSoftShadow,
  },
  alertCardCompact: {
    alignItems: "stretch",
  },
  alertHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    flex: 1,
    minWidth: 260,
  },
  alertIcon: {
    width: 42,
    height: 42,
    borderRadius: 21,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(255,255,255,0.72)",
  },
  alertInfo: {
    flex: 1,
  },
  alertTitle: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: "700",
    color: "#92400E",
  },
  alertText: {
    fontSize: typography.fontSize.caption,
    color: "#78350F",
  },
  alertButton: {
    backgroundColor: doctorPalette.primary,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: doctorRadii.pill,
  },
  alertButtonText: {
    color: doctorPalette.surface,
    fontSize: typography.fontSize.bodySmall,
    fontWeight: "800",
  },
  section: {
    backgroundColor: doctorPalette.surface,
    borderRadius: doctorRadii.xl,
    borderWidth: 1,
    borderColor: doctorPalette.border,
    padding: spacing.md,
    gap: spacing.md,
    ...doctorSoftShadow,
  },
  sectionHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: spacing.sm,
    flexWrap: "wrap",
  },
  sectionTitle: {
    fontSize: typography.fontSize.body,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  viewAllText: {
    fontSize: typography.fontSize.caption,
    fontWeight: "800",
    color: doctorPalette.primary,
  },
  patientList: {
    gap: spacing.xs,
  },
  patientRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.sm,
    borderRadius: doctorRadii.md,
    backgroundColor: doctorPalette.surfaceSoft,
    borderWidth: 1,
    borderColor: doctorPalette.border,
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  patientRowLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    flex: 1,
    minWidth: 0,
  },
  avatarPill: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: doctorPalette.surfaceLime,
    alignItems: "center",
    justifyContent: "center",
  },
  avatarInitial: {
    fontSize: 16,
    fontWeight: "700",
    color: doctorPalette.ink,
  },
  patientIdentity: {
    flex: 1,
    minWidth: 0,
  },
  patientName: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  patientMeta: {
    fontSize: typography.fontSize.caption,
    color: doctorPalette.muted,
  },
  patientRowRight: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    flexWrap: "wrap",
  },
  openPatientAction: {
    fontSize: typography.fontSize.caption,
    fontWeight: "800",
    color: doctorPalette.primary,
  },
  referenceCard: {
    backgroundColor: doctorPalette.surface,
    borderRadius: doctorRadii.lg,
    borderWidth: 1,
    borderColor: doctorPalette.border,
    padding: spacing.md,
    gap: 4,
  },
  referenceTitle: {
    fontSize: typography.fontSize.caption,
    fontWeight: "800",
    color: doctorPalette.muted,
  },
  referenceText: {
    fontSize: 11,
    color: doctorPalette.muted,
    lineHeight: 16,
  },
});
