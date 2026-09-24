import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { doctorPalette, doctorSoftShadow } from "../doctorDesign";
import { SectionHeader, HomeInlineState } from "./DoctorHomeBits";

export function MonitoringStatusCard({
  upToDate,
  limited,
  noRecentData,
  analyzed,
}: {
  upToDate: number;
  limited: number;
  noRecentData: number;
  analyzed: number;
}) {
  const total = analyzed;
  const hasAny = total > 0;

  return (
    <View style={styles.section}>
      <SectionHeader title="Monitoring Status" viewAllLabel="Open directory" />
      <View style={styles.card}>
        {!hasAny ? (
          <HomeInlineState
            icon="pulse-outline"
            title="No monitoring data"
            message="We'll start showing monitoring coverage once glucose readings are received."
          />
        ) : (
          <>
            <View style={styles.coverageRow}>
              <View style={styles.coverageIcon}>
                <Ionicons name="pulse" size={17} color={doctorPalette.primary} />
              </View>
              <View style={styles.coverageText}>
                <Text style={styles.coverageTitle} allowFontScaling>
                  {upToDate} of {total} patients
                </Text>
                <Text style={styles.coverageSub} allowFontScaling>
                  have continuous monitoring coverage (≥70% of last 30 days)
                </Text>
              </View>
            </View>
            <View style={styles.barTrack}>
              {upToDate > 0 ? <View style={[styles.barSeg, { flex: upToDate, backgroundColor: "#10B981" }]} /> : null}
              {limited > 0 ? <View style={[styles.barSeg, { flex: limited, backgroundColor: "#F59E0B" }]} /> : null}
              {noRecentData > 0 ? <View style={[styles.barSeg, { flex: noRecentData, backgroundColor: "#CBD5E1" }]} /> : null}
            </View>
            <View style={styles.legendRow}>
              <LegendDot color="#10B981" label={`Up to date (${upToDate})`} />
              <LegendDot color="#F59E0B" label={`Limited (${limited})`} />
              <LegendDot color="#CBD5E1" label={`No recent (${noRecentData})`} />
            </View>
          </>
        )}
      </View>
    </View>
  );
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <View style={styles.legendItem} accessible accessibilityRole="text" accessibilityLabel={label}>
      <View style={[styles.dot, { backgroundColor: color }]} />
      <Text style={styles.legendText} allowFontScaling>
        {label}
      </Text>
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
  coverageRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  coverageIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: doctorPalette.surfaceBlue,
    alignItems: "center",
    justifyContent: "center",
  },
  coverageText: {
    flex: 1,
  },
  coverageTitle: {
    fontSize: 15,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  coverageSub: {
    fontSize: 12,
    lineHeight: 16,
    color: doctorPalette.muted,
    marginTop: 1,
  },
  barTrack: {
    flexDirection: "row",
    height: 10,
    borderRadius: 5,
    overflow: "hidden",
    backgroundColor: doctorPalette.surfaceSoft,
  },
  barSeg: {
    height: "100%",
  },
  legendRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "space-between",
    gap: 8,
  },
  legendItem: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  legendText: {
    fontSize: 11,
    fontWeight: "700",
    color: doctorPalette.inkSecondary,
  },
});