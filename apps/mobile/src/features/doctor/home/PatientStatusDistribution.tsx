import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { doctorPalette, doctorSoftShadow } from "../doctorDesign";
import { SectionHeader, HomeInlineState } from "./DoctorHomeBits";

interface Distribution {
  controlled: number;
  watch: number;
  needsReview: number;
  urgentReview: number;
  analyzed: number;
}

const BUCKETS = [
  { key: "controlled" as const, label: "Controlled", color: "#10B981" },
  { key: "watch" as const, label: "Watch", color: "#F59E0B" },
  { key: "needsReview" as const, label: "Needs Review", color: "#F97316" },
  { key: "urgentReview" as const, label: "Urgent Review", color: "#EF4444" },
];

export function PatientStatusDistribution({
  distribution,
  analyzedCount,
  onViewAll,
}: {
  distribution: Distribution;
  analyzedCount: number;
  onViewAll?: () => void;
}) {
  const total = distribution.analyzed;

  return (
    <View style={styles.section}>
      <SectionHeader title="Patient Status Distribution" viewAllLabel="Open directory" onViewAll={onViewAll} />
      <View style={styles.card}>
        {total === 0 ? (
          <HomeInlineState
            icon="pie-chart-outline"
            title="No statuses to show"
            message="Statuses are derived from confirmed glucose data. They will populate once readings are available."
          />
        ) : (
          <>
            <View style={styles.legendList}>
              {BUCKETS.map((bucket) => (
                <View key={bucket.key} style={styles.legendRow}>
                  <View style={styles.legendLeft}>
                    <View style={[styles.legendDot, { backgroundColor: bucket.color }]} />
                    <Text style={styles.legendLabel} allowFontScaling>
                      {bucket.label}
                    </Text>
                  </View>
                  <Text style={styles.legendCount} allowFontScaling>
                    {distribution[bucket.key]}
                  </Text>
                </View>
              ))}
            </View>
            <View style={styles.barTrack}>
              {BUCKETS.map((bucket) => {
                const count = distribution[bucket.key];
                return count > 0 ? (
                  <View
                    key={bucket.key}
                    style={[
                      styles.barSegment,
                      { flex: count, backgroundColor: bucket.color },
                    ]}
                  />
                ) : null;
              })}
            </View>
            <Text style={styles.caption} allowFontScaling>
              Based on ADA/EASD targets · {total} of {analyzedCount} analyzed patients
            </Text>
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
    gap: 14,
    ...doctorSoftShadow,
  },
  legendList: {
    gap: 10,
  },
  legendRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  legendLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  legendDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  legendLabel: {
    fontSize: 13,
    fontWeight: "700",
    color: doctorPalette.inkSecondary,
  },
  legendCount: {
    fontSize: 14,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  barTrack: {
    flexDirection: "row",
    height: 12,
    borderRadius: 6,
    overflow: "hidden",
    backgroundColor: doctorPalette.surfaceSoft,
  },
  barSegment: {
    height: "100%",
  },
  caption: {
    fontSize: 11,
    fontWeight: "600",
    color: doctorPalette.muted,
    textAlign: "center",
  },
});