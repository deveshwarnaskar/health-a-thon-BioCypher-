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
import type { MonthlyReportData } from "../../types";

export type MonthlyReportViewerProps = {
  visible: boolean;
  onClose: () => void;
  report: MonthlyReportData | null;
};

export function MonthlyReportViewer({ visible, onClose, report }: MonthlyReportViewerProps) {
  const { isOffline, isSyncing } = useConnectivity();
  const [showEvidence, setShowEvidence] = useState(false);

  if (!report) return null;

  const hasTrendData =
    report.glucoseTrend.week1Avg !== null ||
    report.glucoseTrend.week2Avg !== null ||
    report.glucoseTrend.week3Avg !== null ||
    report.glucoseTrend.week4Avg !== null;

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
                MONTHLY HEALTH SUMMARY
              </Text>
            </View>
            <Text style={styles.headerTitle} allowFontScaling numberOfLines={1}>
              {report.monthName} {report.year} Patient Summary
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
          {/* Month Overview Card */}
          <View style={styles.overviewCard}>
            <View style={styles.summaryBadgeRow}>
              <View style={[styles.summaryBadge, isOffline && styles.summaryBadgeOffline]}>
                <Ionicons
                  name={isOffline ? "cloud-offline-outline" : "information-circle-outline"}
                  size={13}
                  color={isOffline ? "#92400E" : "#6B21A8"}
                />
                <Text
                  style={[styles.summaryBadgeText, isOffline && styles.summaryBadgeTextOffline]}
                  allowFontScaling
                >
                  {isOffline ? "Offline summary" : "Patient Summary"}
                </Text>
              </View>
            </View>

            <Text style={styles.overviewKicker} allowFontScaling>
              {report.monthName.toUpperCase()} AT A GLANCE
            </Text>
            <Text style={styles.overviewTitle} allowFontScaling>
              Longitudinal Monthly Patient Summary
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

          {/* Section 1: Monthly Averages */}
          <View style={styles.sectionCard}>
            <Text style={styles.sectionKicker} allowFontScaling>MONTHLY AGGREGATES</Text>
            <View style={styles.metricsGrid}>
              <View style={styles.metricTile}>
                <Text style={styles.metricVal} allowFontScaling>
                  {report.averageGlucoseMgDl ? `${report.averageGlucoseMgDl}` : "--"}
                </Text>
                <Text style={styles.metricUnit} allowFontScaling>mg/dL</Text>
                <Text style={styles.metricLabel} allowFontScaling>Monthly Mean</Text>
              </View>

              <View style={styles.metricTile}>
                <Text style={styles.metricVal} allowFontScaling>
                  {report.totalReadings}
                </Text>
                <Text style={styles.metricUnit} allowFontScaling>readings</Text>
                <Text style={styles.metricLabel} allowFontScaling>Glucose Logs</Text>
              </View>

              <View style={styles.metricTile}>
                <Text style={styles.metricVal} allowFontScaling>
                  {report.medicationAdherencePct}%
                </Text>
                <Text style={styles.metricUnit} allowFontScaling>adherence</Text>
                <Text style={styles.metricLabel} allowFontScaling>Medication Taken</Text>
              </View>

              <View style={styles.metricTile}>
                <Text style={styles.metricVal} allowFontScaling>
                  {report.totalMealsLogged}
                </Text>
                <Text style={styles.metricUnit} allowFontScaling>meals</Text>
                <Text style={styles.metricLabel} allowFontScaling>Nutrition Logs</Text>
              </View>
            </View>
          </View>

          {/* Section 2: 4-Week Trend */}
          <View style={styles.sectionCard}>
            <Text style={styles.sectionKicker} allowFontScaling>WEEKLY GLUCOSE PROGRESSION</Text>
            {hasTrendData ? (
              <View style={styles.trendList}>
                {[
                  { w: "Week 1", v: report.glucoseTrend.week1Avg },
                  { w: "Week 2", v: report.glucoseTrend.week2Avg },
                  { w: "Week 3", v: report.glucoseTrend.week3Avg },
                  { w: "Week 4", v: report.glucoseTrend.week4Avg },
                ].map((item) => (
                  <View key={item.w} style={styles.trendRow}>
                    <Text style={styles.trendWeek} allowFontScaling>{item.w}</Text>
                    {item.v !== null ? (
                      <View style={styles.trendBarContainer}>
                        <View style={[styles.trendBar, { width: `${Math.min(100, (item.v / 250) * 100)}%` }]} />
                        <Text style={styles.trendVal} allowFontScaling>{item.v} mg/dL</Text>
                      </View>
                    ) : (
                      <Text style={styles.noDataText} allowFontScaling>Insufficient data</Text>
                    )}
                  </View>
                ))}
              </View>
            ) : (
              <View style={styles.insufficientBox}>
                <Ionicons name="bar-chart-outline" size={24} color="#94A3B8" />
                <Text style={styles.insufficientText} allowFontScaling>
                  Not enough recorded data across weeks to show a longitudinal trend.
                </Text>
              </View>
            )}
          </View>

          {/* Section 3: Repeated Observations across the Month */}
          <View style={styles.sectionCard}>
            <Text style={styles.sectionKicker} allowFontScaling>REPEATED OBSERVATIONS</Text>
            {report.repeatedObservations.map((obs, idx) => (
              <View key={idx} style={styles.obsRow}>
                <Ionicons name="repeat-outline" size={16} color="#0284C7" />
                <Text style={styles.obsText} allowFontScaling>{obs}</Text>
              </View>
            ))}

            <TouchableOpacity
              style={styles.evidenceBtn}
              onPress={() => setShowEvidence(true)}
              accessibilityRole="button"
              accessibilityLabel="View supporting records"
            >
              <Ionicons name="search-outline" size={16} color="#0284C7" />
              <Text style={styles.evidenceBtnText} allowFontScaling>
                Inspect supporting records ({report.evidenceItems.length})
              </Text>
            </TouchableOpacity>
          </View>

          {/* Section 4: Discussion Topics */}
          <View style={styles.sectionCard}>
            <Text style={styles.sectionKicker} allowFontScaling>TOPICS TO DISCUSS WITH YOUR DOCTOR</Text>
            {report.clinicianDiscussionTopics.map((topic, idx) => (
              <View key={idx} style={styles.topicRow}>
                <Ionicons name="help-circle-outline" size={16} color="#4F46E5" />
                <Text style={styles.topicText} allowFontScaling>{topic}</Text>
              </View>
            ))}
          </View>

          {/* Section 5: Safety Guardrails */}
          <View style={styles.safetyCard}>
            <Text style={styles.safetyHeader} allowFontScaling>PATIENT HEALTH SUMMARY</Text>
            <Text style={styles.safetyText} allowFontScaling>
              This monthly summary is a patient-facing compilation of your recorded observations. It is not an official clinician-certified report or clinical diagnosis. Do not make medication changes or treatment adjustments without consulting your doctor.
            </Text>
          </View>

          <View style={{ height: 40 }} />
        </ScrollView>

        <EvidenceDrawer
          visible={showEvidence}
          onClose={() => setShowEvidence(false)}
          title={`Monthly Supporting Records · ${report.monthName}`}
          items={report.evidenceItems}
          basisText={`Derived from ${report.evidenceItems.length} patient observations during ${report.monthName} ${report.year}.`}
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
    backgroundColor: "#7C3AED",
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
    backgroundColor: "#FAF5FF",
    borderRadius: radii.lg,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: "#E9D5FF",
    marginBottom: spacing.md,
  },
  overviewKicker: {
    ...typography.caption,
    color: "#7E22CE",
    fontWeight: "700",
    letterSpacing: 0.5,
  },
  overviewTitle: {
    ...typography.titleLarge,
    color: "#581C87",
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
    backgroundColor: "#F3E8FF",
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: "#E9D5FF",
  },
  summaryBadgeOffline: {
    backgroundColor: "#FEF3C7",
    borderColor: "#FDE68A",
  },
  summaryBadgeText: {
    ...typography.caption,
    color: "#6B21A8",
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
    borderTopColor: "#E9D5FF",
  },
  provenancePrimaryText: {
    ...typography.caption,
    color: "#581C87",
    fontWeight: "700",
  },
  provenanceNoticeText: {
    ...typography.caption,
    color: "#7E22CE",
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
  trendList: {
    gap: spacing.sm,
  },
  trendRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  trendWeek: {
    width: 64,
    ...typography.caption,
    color: "#475569",
    fontWeight: "700",
  },
  trendBarContainer: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  trendBar: {
    height: 10,
    backgroundColor: "#0284C7",
    borderRadius: 5,
  },
  trendVal: {
    ...typography.caption,
    color: colors.textPrimary,
    fontWeight: "600",
  },
  noDataText: {
    ...typography.caption,
    color: "#94A3B8",
    fontStyle: "italic",
  },
  insufficientBox: {
    alignItems: "center",
    padding: spacing.lg,
    backgroundColor: "#F8FAFC",
    borderRadius: radii.md,
  },
  insufficientText: {
    ...typography.caption,
    color: "#64748B",
    marginTop: spacing.xs,
    textAlign: "center",
  },
  obsRow: {
    flexDirection: "row",
    gap: spacing.sm,
    marginBottom: spacing.sm,
    alignItems: "flex-start",
  },
  obsText: {
    ...typography.bodyMedium,
    color: "#334155",
    flex: 1,
    lineHeight: 20,
  },
  evidenceBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    marginTop: spacing.xs,
  },
  evidenceBtnText: {
    ...typography.caption,
    color: "#0284C7",
    fontWeight: "700",
  },
  topicRow: {
    flexDirection: "row",
    gap: spacing.sm,
    marginBottom: spacing.sm,
    alignItems: "flex-start",
  },
  topicText: {
    ...typography.bodyMedium,
    color: "#334155",
    flex: 1,
  },
  safetyCard: {
    backgroundColor: "#F8FAFC",
    borderRadius: radii.md,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    marginBottom: spacing.lg,
  },
  safetyHeader: {
    ...typography.caption,
    color: "#64748B",
    fontWeight: "700",
    marginBottom: spacing.xs,
  },
  safetyText: {
    ...typography.caption,
    color: "#64748B",
    lineHeight: 18,
  },
});
