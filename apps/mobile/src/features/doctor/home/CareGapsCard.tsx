import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { doctorPalette, doctorSoftShadow } from "../doctorDesign";
import { SectionHeader, HomeInlineState } from "./DoctorHomeBits";

export interface CareGapRow {
  key: string;
  label: string;
  count: number;
}

export const DEFAULT_CARE_GAP_COUNTS = {
  a1c: 0,
  bloodPressure: 0,
  kidney: 0,
  retinal: 0,
  foot: 0,
  lipid: 0,
  other: 0,
  total: 0,
  matched: false,
};

const ROWS: CareGapRow[] = [
  { key: "a1c", label: "A1C Review", count: 0 },
  { key: "bloodPressure", label: "Blood Pressure", count: 0 },
  { key: "kidney", label: "Kidney / Albuminuria", count: 0 },
  { key: "retinal", label: "Retinal Screening", count: 0 },
  { key: "foot", label: "Foot Exam", count: 0 },
  { key: "lipid", label: "Lipids", count: 0 },
  { key: "other", label: "Other", count: 0 },
];

export function CareGapsCard({
  counts,
  totalTasks,
  onViewAll,
  isLoading,
  hasNumericData,
}: {
  counts: {
    a1c: number;
    bloodPressure: number;
    kidney: number;
    retinal: number;
    foot: number;
    lipid: number;
    other: number;
    total: number;
    matched: boolean;
  };
  totalTasks: number;
  onViewAll?: () => void;
  isLoading?: boolean;
  hasNumericData?: boolean;
}) {
  const countFor = (key: string): number => {
    switch (key) {
      case "a1c":
        return counts.a1c;
      case "bloodPressure":
        return counts.bloodPressure;
      case "kidney":
        return counts.kidney;
      case "retinal":
        return counts.retinal;
      case "foot":
        return counts.foot;
      case "lipid":
        return counts.lipid;
      default:
        return counts.other;
    }
  };

  const rows = ROWS.map((row) => ({ ...row, count: countFor(row.key) })).filter((row) => row.count > 0);

  return (
    <View style={styles.section}>
      <SectionHeader title="Care Gaps" viewAllLabel="Open care tasks" onViewAll={onViewAll} />
      <View style={styles.card}>
        {isLoading ? (
          <Text style={styles.loadingText} allowFontScaling>
            Loading care tasks…
          </Text>
        ) : totalTasks === 0 || !hasNumericData ? (
          <HomeInlineState
            icon="clipboard-outline"
            title="No open care gaps"
            message="Open care tasks will be grouped by category here as they are created. Nothing is pending right now."
          />
        ) : (
          <>
            <View style={styles.headRow}>
              <Text style={styles.headTitle} allowFontScaling>
                {counts.total} open care items
              </Text>
              <Text style={styles.headHint} allowFontScaling>
                Grouped from your care tasks
              </Text>
            </View>
            {rows.map((row) => (
              <View key={row.key} style={styles.row}>
                <Text style={styles.rowLabel} allowFontScaling numberOfLines={1}>
                  {row.label}
                </Text>
                <View style={styles.rowCountWrap}>
                  <Text style={styles.rowCount} allowFontScaling>
                    {row.count}
                  </Text>
                </View>
              </View>
            ))}
          </>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  section: {
    gap: 12,
  },
  card: {
    backgroundColor: doctorPalette.surface,
    borderRadius: 24,
    borderWidth: 1,
    borderColor: doctorPalette.borderSubtle,
    padding: 18,
    gap: 10,
    ...doctorSoftShadow,
  },
  loadingText: {
    fontSize: 13,
    fontWeight: "600",
    color: doctorPalette.muted,
  },
  headRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 2,
  },
  headTitle: {
    fontSize: 14,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  headHint: {
    fontSize: 11,
    fontWeight: "600",
    color: doctorPalette.muted,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: 8,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: doctorPalette.borderSubtle,
  },
  rowLabel: {
    fontSize: 13,
    fontWeight: "700",
    color: doctorPalette.inkSecondary,
    flex: 1,
  },
  rowCountWrap: {
    minWidth: 28,
    height: 28,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: doctorPalette.surfaceLime,
  },
  rowCount: {
    fontSize: 13,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
});