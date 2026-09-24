import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { doctorPalette, doctorRadii, doctorSoftShadow } from "../doctorDesign";
import { SectionHeader } from "./DoctorHomeBits";

const REPORTS = [
  {
    key: "agp",
    label: "Ambulatory Glucose Profile (AGP)",
    subLabel: "TIR, TAR, TBR, GMI & glycemic patterns",
    badge: "ADA/EASD",
    icon: "water-outline" as const,
    tint: "#10B981",
  },
  {
    key: "glycemic",
    label: "Longitudinal Glycemic Trajectory",
    subLabel: "7D / 30D / 90D deterministic comparisons",
    badge: "Deterministic",
    icon: "stats-chart-outline" as const,
    tint: doctorPalette.primary,
  },
  {
    key: "renal",
    label: "Renal & Cardiometabolic Screening",
    subLabel: "eGFR, UACR, blood pressure & BMI",
    badge: "Comprehensive",
    icon: "heart-outline" as const,
    tint: "#8B5CF6",
  },
];

export function ReportsSummaryCard({
  onOpen,
  lastSyncedDays,
}: {
  onOpen: () => void;
  lastSyncedDays: number | null;
}) {
  return (
    <View style={styles.section}>
      <SectionHeader title="Official Clinical Reports" viewAllLabel="Open reports" onViewAll={onOpen} />
      <Pressable
        style={({ pressed }) => [styles.card, pressed && styles.cardPressed]}
        onPress={onOpen}
        accessibilityRole="button"
        accessibilityLabel="Open clinical reports and download official PDF"
      >
        <View style={styles.cardHeader}>
          <View style={styles.headerIconWrap}>
            <Ionicons name="document-text" size={18} color={doctorPalette.primary} />
          </View>
          <View style={styles.headerText}>
            <View style={styles.titleRow}>
              <Text style={styles.cardTitle} allowFontScaling numberOfLines={1}>
                Downloadable PDF Reports
              </Text>
              <View style={styles.readyBadge}>
                <Ionicons name="download-outline" size={11} color={doctorPalette.primary} />
                <Text style={styles.readyBadgeText} allowFontScaling>
                  PDF Engine
                </Text>
              </View>
            </View>
            <Text style={styles.cardSubtitle} allowFontScaling numberOfLines={1}>
              Audit-ready clinical documentation with deterministic math
            </Text>
          </View>
        </View>

        <View style={styles.list}>
          {REPORTS.map((report) => (
            <View key={report.key} style={styles.row}>
              <View style={[styles.rowIcon, { backgroundColor: `${report.tint}18` }]}>
                <Ionicons name={report.icon} size={15} color={report.tint} />
              </View>
              <View style={styles.rowTextCol}>
                <View style={styles.rowTitleLine}>
                  <Text style={styles.rowLabel} allowFontScaling numberOfLines={1}>
                    {report.label}
                  </Text>
                  <View style={styles.reportBadge}>
                    <Text style={styles.reportBadgeText} allowFontScaling>
                      {report.badge}
                    </Text>
                  </View>
                </View>
                <Text style={styles.rowSubLabel} allowFontScaling numberOfLines={1}>
                  {report.subLabel}
                </Text>
              </View>
              <Ionicons name="chevron-forward" size={16} color={doctorPalette.muted} />
            </View>
          ))}
        </View>

        <View style={styles.footerRow}>
          <Text style={styles.meta} allowFontScaling>
            {lastSyncedDays === null
              ? "Deterministic calculations • Exportable & shareable PDF"
              : `Last synced ${lastSyncedDays} day${lastSyncedDays === 1 ? "" : "s"} ago`}
          </Text>
        </View>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  section: {
    gap: 12,
  },
  card: {
    backgroundColor: doctorPalette.surface,
    borderRadius: 22,
    borderWidth: 1,
    borderColor: doctorPalette.borderSubtle,
    padding: 16,
    gap: 12,
    ...doctorSoftShadow,
  },
  cardPressed: {
    opacity: 0.86,
    backgroundColor: doctorPalette.surfaceSoft,
  },
  cardHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  headerIconWrap: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: doctorPalette.surfaceBlue,
    alignItems: "center",
    justifyContent: "center",
  },
  headerText: {
    flex: 1,
    gap: 2,
  },
  titleRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 8,
  },
  cardTitle: {
    fontSize: 14,
    fontWeight: "800",
    color: doctorPalette.ink,
    letterSpacing: -0.2,
    flexShrink: 1,
  },
  readyBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    backgroundColor: doctorPalette.surfaceBlue,
    borderRadius: doctorRadii.pill,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderWidth: 1,
    borderColor: "#BFDBFE",
  },
  readyBadgeText: {
    fontSize: 10,
    fontWeight: "800",
    color: doctorPalette.primary,
  },
  cardSubtitle: {
    fontSize: 11,
    fontWeight: "600",
    color: doctorPalette.muted,
  },
  list: {
    gap: 6,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingVertical: 8,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: doctorPalette.borderSubtle,
  },
  rowIcon: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center",
  },
  rowTextCol: {
    flex: 1,
    gap: 2,
  },
  rowTitleLine: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 6,
  },
  rowLabel: {
    fontSize: 13,
    fontWeight: "700",
    color: doctorPalette.ink,
    flexShrink: 1,
  },
  reportBadge: {
    backgroundColor: doctorPalette.surfaceSoft,
    borderRadius: 6,
    paddingHorizontal: 5,
    paddingVertical: 2,
  },
  reportBadgeText: {
    fontSize: 9,
    fontWeight: "800",
    color: doctorPalette.inkSecondary,
  },
  rowSubLabel: {
    fontSize: 11,
    fontWeight: "500",
    color: doctorPalette.muted,
  },
  footerRow: {
    alignItems: "center",
    paddingTop: 2,
  },
  meta: {
    fontSize: 11,
    fontWeight: "600",
    color: doctorPalette.muted,
    textAlign: "center",
  },
});