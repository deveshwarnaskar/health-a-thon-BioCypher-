import React, { useState } from "react";
import {
  Modal,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors, radii, spacing, touchTarget, typography } from "../../../../theming/tokens";
import { useConnectivity } from "../../../../connectivity/useConnectivity";
import { EvidenceDrawer } from "./EvidenceDrawer";
import type { WeeklyReportData, EvidenceItem } from "../../types";

export type WeeklyReportViewerProps = {
  visible: boolean;
  onClose: () => void;
  report: WeeklyReportData | null;
};

export function WeeklyReportViewer({ visible, onClose, report }: WeeklyReportViewerProps) {
  const { isOffline, isSyncing } = useConnectivity();
  const [selectedEvidence, setSelectedEvidence] = useState<{
    title: string;
    items: EvidenceItem[];
    basisText?: string;
  } | null>(null);

  if (!report) return null;

  return (
    <Modal visible={visible} animationType="slide" transparent={false} onRequestClose={onClose}>
      <View style={styles.container}>
        {/* Top Header */}
        <View style={styles.header}>
          <TouchableOpacity
            onPress={onClose}
            style={styles.backButton}
            accessibilityRole="button"
            accessibilityLabel="Back to reports"
            activeOpacity={0.7}
          >
            <Ionicons name="arrow-back" size={20} color="#0F172A" />
          </TouchableOpacity>
          <View style={styles.headerTitleCol}>
            <View style={styles.kickerRow}>
              <View style={styles.kickerDot} />
              <Text style={styles.headerKicker} allowFontScaling>
                WEEKLY HEALTH SUMMARY
              </Text>
            </View>
            <Text style={styles.headerTitle} allowFontScaling numberOfLines={1}>
              Week {report.weekNumber} Patient Summary
            </Text>
          </View>
          <View style={styles.sharingPill}>
            <Ionicons
              name={report.sharingStatus === "shared" ? "checkmark-circle" : "eye-outline"}
              size={13}
              color={report.sharingStatus === "shared" ? "#059669" : "#64748B"}
            />
            <Text
              style={[
                styles.sharingText,
                { color: report.sharingStatus === "shared" ? "#059669" : "#64748B" },
              ]}
              allowFontScaling
            >
              {report.sharingStatus === "shared" ? "Shared" : "Private"}
            </Text>
          </View>
        </View>

        <ScrollView style={styles.content} showsVerticalScrollIndicator={false}>
          {/* Week Overview Card */}
          <View style={styles.overviewCard}>
            <View style={styles.summaryBadgeRow}>
              <View style={[styles.summaryBadge, isOffline && styles.summaryBadgeOffline]}>
                <Ionicons
                  name={isOffline ? "cloud-offline-outline" : "information-circle-outline"}
                  size={13}
                  color={isOffline ? "#B45309" : "#0F766E"}
                />
                <Text
                  style={[styles.summaryBadgeText, isOffline && styles.summaryBadgeTextOffline]}
                  allowFontScaling
                >
                  {isOffline ? "Offline summary" : "Patient Summary"}
                </Text>
              </View>
            </View>

            <Text style={styles.overviewDate} allowFontScaling>{report.dateRange}</Text>
            <Text style={styles.overviewTitle} allowFontScaling>
              7-Day Patient Health Summary
            </Text>

            <View style={styles.provenanceBox}>
              <Text style={styles.provenancePrimaryText} allowFontScaling>
                Calculated on this device from currently available records.
              </Text>
              {isOffline ? (
                <Text style={styles.provenanceNoticeText} allowFontScaling>
                  This summary uses records currently available on this device. Records that have not synchronized yet may not be included.
                </Text>
              ) : isSyncing ? (
                <Text style={styles.provenanceNoticeText} allowFontScaling>
                  Some records may still be waiting to sync.
                </Text>
              ) : (
                <Text style={styles.provenanceNoticeText} allowFontScaling>
                  Calculated from your currently available records. Some records may still be waiting to sync.
                </Text>
              )}
            </View>
          </View>

          {/* Section 1: Data Coverage */}
          <View style={styles.sectionCard}>
            <Text style={styles.sectionKicker} allowFontScaling>DATA COVERAGE</Text>
            <View style={styles.coverageRow}>
              <View style={styles.coverageTextCol}>
                <Text style={styles.coverageTitle} allowFontScaling>
                  {report.dataCoverage.loggedDays} of {report.dataCoverage.totalDays} Days Recorded
                </Text>
                <Text style={styles.coverageSubtext} allowFontScaling>
                  Data recording completeness indicator (not a clinical score)
                </Text>
              </View>
              <View style={styles.coverageBadge}>
                <Text style={styles.coveragePct} allowFontScaling>
                  {report.dataCoverage.percentage}%
                </Text>
              </View>
            </View>
          </View>

          {/* Section 2: Glucose Metrics */}
          <View style={styles.sectionCard}>
            <Text style={styles.sectionKicker} allowFontScaling>GLUCOSE METRICS</Text>
            <View style={styles.metricsGrid}>
              <View style={styles.metricTile}>
                <Text style={styles.metricVal} allowFontScaling>
                  {report.glucoseMetrics.averageMgDl ? `${report.glucoseMetrics.averageMgDl}` : "--"}
                </Text>
                <Text style={styles.metricUnit} allowFontScaling>mg/dL</Text>
                <Text style={styles.metricLabel} allowFontScaling>Average Glucose</Text>
              </View>

              <View style={styles.metricTile}>
                <Text style={styles.metricVal} allowFontScaling>
                  {report.glucoseMetrics.totalReadings}
                </Text>
                <Text style={styles.metricUnit} allowFontScaling>readings</Text>
                <Text style={styles.metricLabel} allowFontScaling>Total Logs</Text>
              </View>

              <View style={styles.metricTile}>
                <Text style={styles.metricVal} allowFontScaling>
                  {report.glucoseMetrics.fastingAverageMgDl ? `${report.glucoseMetrics.fastingAverageMgDl}` : "--"}
                </Text>
                <Text style={styles.metricUnit} allowFontScaling>mg/dL</Text>
                <Text style={styles.metricLabel} allowFontScaling>Fasting Avg</Text>
              </View>

              <View style={styles.metricTile}>
                <Text style={styles.metricVal} allowFontScaling>
                  {report.glucoseMetrics.postMealAverageMgDl ? `${report.glucoseMetrics.postMealAverageMgDl}` : "--"}
                </Text>
                <Text style={styles.metricUnit} allowFontScaling>mg/dL</Text>
                <Text style={styles.metricLabel} allowFontScaling>Post-Meal Avg</Text>
              </View>
            </View>

            {report.glucoseMetrics.timeInRangePct !== null ? (
              <View style={styles.tirContainer}>
                <Text style={styles.tirLabel} allowFontScaling>Time In Range (70-180 mg/dL): {report.glucoseMetrics.timeInRangePct}%</Text>
                <View style={styles.tirBar}>
                  <View style={[styles.tirSegment, { flex: report.glucoseMetrics.timeBelowRangePct || 0, backgroundColor: "#EF4444" }]} />
                  <View style={[styles.tirSegment, { flex: report.glucoseMetrics.timeInRangePct || 0, backgroundColor: "#10B981" }]} />
                  <View style={[styles.tirSegment, { flex: report.glucoseMetrics.timeAboveRangePct || 0, backgroundColor: "#F59E0B" }]} />
                </View>
              </View>
            ) : null}
          </View>

          {/* Section 3: Meals, Medication & Activity */}
          <View style={styles.sectionCard}>
            <Text style={styles.sectionKicker} allowFontScaling>LIFESTYLE & ADHERENCE</Text>
            <View style={styles.lifestyleRow}>
              <View style={styles.lifestyleItem}>
                <Ionicons name="restaurant-outline" size={20} color="#D97706" />
                <Text style={styles.lifestyleVal} allowFontScaling>{report.mealsSummary.totalLogged} Meals</Text>
                <Text style={styles.lifestyleSub} allowFontScaling>{report.mealsSummary.daysWithMeals} days logged</Text>
              </View>
              <View style={styles.lifestyleItem}>
                <Ionicons name="medkit-outline" size={20} color="#2563EB" />
                <Text style={styles.lifestyleVal} allowFontScaling>{report.medicationAdherence.adherencePct}% Taken</Text>
                <Text style={styles.lifestyleSub} allowFontScaling>{report.medicationAdherence.missedDoses} missed</Text>
              </View>
              <View style={styles.lifestyleItem}>
                <Ionicons name="walk-outline" size={20} color="#059669" />
                <Text style={styles.lifestyleVal} allowFontScaling>{report.activitySummary.totalMinutes} min</Text>
                <Text style={styles.lifestyleSub} allowFontScaling>{report.activitySummary.activeDays} active days</Text>
              </View>
            </View>
          </View>

          {/* Section 4: Observed Patterns (Evidence Grounded) */}
          <View style={styles.sectionCard}>
            <Text style={styles.sectionKicker} allowFontScaling>OBSERVED PATTERNS</Text>
            {report.observedPatterns.map((pat, idx) => (
              <View key={idx} style={styles.patternBox}>
                <Text style={styles.patternTitle} allowFontScaling>{pat.title}</Text>
                <Text style={styles.patternObservation} allowFontScaling>
                  &ldquo;{pat.observationText}&rdquo;
                </Text>
                <Text style={styles.patternEvidence} allowFontScaling>
                  {pat.evidenceText}
                </Text>

                <TouchableOpacity
                  style={styles.evidenceBtn}
                  onPress={() =>
                    setSelectedEvidence({
                      title: pat.title,
                      items: pat.evidenceItems,
                      basisText: pat.evidenceText,
                    })
                  }
                  accessibilityRole="button"
                  accessibilityLabel="View supporting records"
                >
                  <Ionicons name="search-outline" size={16} color="#0284C7" />
                  <Text style={styles.evidenceBtnText} allowFontScaling>View supporting records</Text>
                </TouchableOpacity>
              </View>
            ))}
          </View>

          {/* Section 5: Clinician Questions */}
          <View style={styles.sectionCard}>
            <Text style={styles.sectionKicker} allowFontScaling>QUESTIONS FOR YOUR CLINICIAN</Text>
            <Text style={styles.questionsIntro} allowFontScaling>
              Topics you may wish to discuss during your next consultation:
            </Text>
            {report.clinicianQuestions.map((q, idx) => (
              <View key={idx} style={styles.questionItem}>
                <Ionicons name="chatbubble-ellipses-outline" size={16} color="#4F46E5" />
                <Text style={styles.questionText} allowFontScaling>{q}</Text>
              </View>
            ))}
          </View>

          {/* Section 6: Contextual Limitations & Safety */}
          <View style={styles.limitationsCard}>
            <Text style={styles.limitationsHeader} allowFontScaling>DATA LIMITATIONS & SAFETY</Text>
            <Text style={styles.limitationsText} allowFontScaling>
              {report.contextualLimitations}
            </Text>
            <Text style={styles.disclaimerText} allowFontScaling>
              This patient summary provides observational information only. It is not an official clinician-signed report, and does not provide medical diagnoses, medication changes, or treatment assessments. Consult your doctor for all clinical decisions.
            </Text>
          </View>

          <View style={{ height: 40 }} />
        </ScrollView>

        {/* Evidence Drawer Modal */}
        <EvidenceDrawer
          visible={selectedEvidence !== null}
          onClose={() => setSelectedEvidence(null)}
          title={selectedEvidence?.title || ""}
          items={selectedEvidence?.items || []}
          basisText={selectedEvidence?.basisText}
        />
      </View>
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
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.md,
    paddingTop: 54,
    paddingBottom: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: "#E2E8F0",
    backgroundColor: colors.surface,
  },
  backButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: "#F8FAFC",
    borderWidth: 1,
    borderColor: "#E2E8F0",
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 4,
    elevation: 1,
  },
  headerTitleCol: {
    flex: 1,
    marginLeft: spacing.sm + 2,
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
  headerKicker: {
    fontSize: 10,
    color: "#64748B",
    fontWeight: "700",
    letterSpacing: 1.1,
  },
  headerTitle: {
    fontSize: 18,
    color: "#0F172A",
    fontWeight: "800",
    letterSpacing: -0.3,
  },
  sharingPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    backgroundColor: "#F8FAFC",
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  sharingText: {
    ...typography.caption,
    fontWeight: "700",
  },
  content: {
    flex: 1,
    padding: spacing.lg,
  },
  overviewCard: {
    backgroundColor: "#EFF6FF",
    borderRadius: radii.lg,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: "#BFDBFE",
    marginBottom: spacing.md,
  },
  overviewDate: {
    ...typography.caption,
    color: "#1D4ED8",
    fontWeight: "700",
    textTransform: "uppercase",
  },
  overviewTitle: {
    ...typography.titleLarge,
    color: "#1E3A8A",
    fontWeight: "800",
    marginVertical: spacing.xs,
  },
  summaryBadgeRow: {
    flexDirection: "row",
    marginBottom: spacing.xs,
  },
  summaryBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    backgroundColor: "#CCFBF1",
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: "#99F6E4",
  },
  summaryBadgeOffline: {
    backgroundColor: "#FEF3C7",
    borderColor: "#FDE68A",
  },
  summaryBadgeText: {
    ...typography.caption,
    color: "#0F766E",
    fontWeight: "700",
    fontSize: 11,
  },
  summaryBadgeTextOffline: {
    color: "#92400E",
  },
  provenanceBox: {
    marginTop: spacing.sm,
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: "#DBEAFE",
  },
  provenancePrimaryText: {
    ...typography.caption,
    color: "#1E40AF",
    fontWeight: "700",
  },
  provenanceNoticeText: {
    ...typography.caption,
    color: "#3B82F6",
    marginTop: 2,
    lineHeight: 16,
  },
  sectionCard: {
    backgroundColor: colors.surface,
    borderRadius: radii.lg,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    marginBottom: spacing.md,
  },
  sectionKicker: {
    ...typography.caption,
    color: "#64748B",
    fontWeight: "700",
    letterSpacing: 0.5,
    marginBottom: spacing.md,
  },
  coverageRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  coverageTextCol: {
    flex: 1,
    paddingRight: spacing.sm,
  },
  coverageTitle: {
    ...typography.titleMedium,
    color: colors.textPrimary,
    fontWeight: "700",
  },
  coverageSubtext: {
    ...typography.caption,
    color: "#64748B",
    marginTop: 2,
  },
  coverageBadge: {
    backgroundColor: "#ECFDF5",
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: "#A7F3D0",
  },
  coveragePct: {
    fontSize: 20,
    fontWeight: "800",
    color: "#059669",
  },
  metricsGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  metricTile: {
    width: "48%",
    backgroundColor: "#F8FAFC",
    padding: spacing.md,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: "#F1F5F9",
  },
  metricVal: {
    fontSize: 22,
    fontWeight: "800",
    color: colors.textPrimary,
  },
  metricUnit: {
    ...typography.caption,
    color: "#64748B",
  },
  metricLabel: {
    ...typography.caption,
    color: "#475569",
    fontWeight: "600",
    marginTop: 4,
  },
  tirContainer: {
    marginTop: spacing.md,
  },
  tirLabel: {
    ...typography.caption,
    color: "#334155",
    fontWeight: "600",
    marginBottom: spacing.xs,
  },
  tirBar: {
    height: 12,
    flexDirection: "row",
    borderRadius: 6,
    overflow: "hidden",
  },
  tirSegment: {
    height: "100%",
  },
  lifestyleRow: {
    flexDirection: "row",
    justifyContent: "space-between",
  },
  lifestyleItem: {
    alignItems: "center",
    flex: 1,
  },
  lifestyleVal: {
    ...typography.bodyMedium,
    fontWeight: "700",
    color: colors.textPrimary,
    marginTop: 4,
  },
  lifestyleSub: {
    ...typography.caption,
    color: "#64748B",
    marginTop: 2,
    textAlign: "center",
  },
  patternBox: {
    backgroundColor: "#F8FAFC",
    borderRadius: radii.md,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    marginBottom: spacing.sm,
  },
  patternTitle: {
    ...typography.bodyMedium,
    fontWeight: "700",
    color: colors.textPrimary,
  },
  patternObservation: {
    ...typography.bodyMedium,
    color: "#334155",
    fontStyle: "italic",
    marginVertical: spacing.xs,
  },
  patternEvidence: {
    ...typography.caption,
    color: "#64748B",
    marginBottom: spacing.sm,
  },
  evidenceBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    alignSelf: "flex-start",
  },
  evidenceBtnText: {
    ...typography.caption,
    color: "#0284C7",
    fontWeight: "700",
  },
  questionsIntro: {
    ...typography.caption,
    color: "#64748B",
    marginBottom: spacing.sm,
  },
  questionItem: {
    flexDirection: "row",
    gap: spacing.sm,
    marginBottom: spacing.sm,
    alignItems: "flex-start",
  },
  questionText: {
    ...typography.bodyMedium,
    color: "#334155",
    flex: 1,
  },
  limitationsCard: {
    backgroundColor: "#F8FAFC",
    borderRadius: radii.md,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    marginBottom: spacing.lg,
  },
  limitationsHeader: {
    ...typography.caption,
    color: "#64748B",
    fontWeight: "700",
    marginBottom: spacing.xs,
  },
  limitationsText: {
    ...typography.caption,
    color: "#64748B",
    lineHeight: 18,
    marginBottom: spacing.sm,
  },
  disclaimerText: {
    ...typography.caption,
    color: "#94A3B8",
    fontStyle: "italic",
    lineHeight: 16,
  },
});
