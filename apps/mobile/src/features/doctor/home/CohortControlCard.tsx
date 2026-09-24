import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { doctorPalette, doctorSoftShadow } from "../doctorDesign";
import { SectionHeader, RangeBar, HomeInlineState } from "./DoctorHomeBits";
import type { CohortMetrics } from "../../../services/clinical/cohortClinicalAnalysis";

export function CohortControlCard({
  metrics,
  analyzedCount,
  periodLabel,
  isLoading,
}: {
  metrics: CohortMetrics;
  analyzedCount: number;
  periodLabel: string;
  isLoading: boolean;
}) {
  const hasData = metrics.sampleSize > 0;
  const tir = metrics.tirPct ?? 0;
  const tar = metrics.tarPct ?? 0;
  const tbr = metrics.tbrPct ?? 0;

  return (
    <View style={styles.section}>
      <SectionHeader title="Cohort Glycemic Control" />
      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <View style={styles.titleIcon}>
            <Ionicons name="stats-chart" size={15} color={doctorPalette.primary} />
          </View>
          <Text style={styles.cardTitle} allowFontScaling>
            {periodLabel} · patients in range
          </Text>
          {metrics.sampleSize > 0 ? (
            <Text style={styles.cardMeta} allowFontScaling>
              {metrics.sampleSize}/{analyzedCount} analyzed
            </Text>
          ) : null}
        </View>

        {isLoading ? (
          <Text style={styles.loadingText} allowFontScaling>
            Aggregating patient observations…
          </Text>
        ) : hasData ? (
          <>
            <RangeBar belowPct={tbr} inRangePct={tir} abovePct={tar} />
            <View style={styles.legend}>
              <LegendChip color="#10B981" label={`In range ${tir}%`} />
              <LegendChip color="#F59E0B" label={`Above ${tar}%`} />
              <LegendChip color="#EF4444" label={`Below ${tbr}%`} />
            </View>
            <View style={styles.metricRow}>
              <Metric label="Mean glucose" value={metrics.meanMgDl === null ? "—" : `${metrics.meanMgDl} mg/dL`} />
              <Metric label="GMI" value={metrics.gmiPct === null ? "—" : `${metrics.gmiPct}%`} />
              <Metric label="CV" value={metrics.cvPct === null ? "—" : `${metrics.cvPct}%`} />
            </View>
          </>
        ) : (
          <HomeInlineState
            icon="cloud-offline-outline"
            title="No cohort data yet"
            message="No confirmed readings were found across the analyzed patients for the selected window."
          />
        )}
      </View>
    </View>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.metricCol}>
      <Text style={styles.metricValue} allowFontScaling numberOfLines={1}>
        {value}
      </Text>
      <Text style={styles.metricLabel} allowFontScaling>
        {label}
      </Text>
    </View>
  );
}

function LegendChip({ color, label }: { color: string; label: string }) {
  return (
    <View style={styles.legendChip} accessible accessibilityRole="text" accessibilityLabel={label}>
      <View style={[styles.legendDot, { backgroundColor: color }]} />
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
  cardHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  titleIcon: {
    width: 26,
    height: 26,
    borderRadius: 13,
    backgroundColor: doctorPalette.surfaceBlue,
    alignItems: "center",
    justifyContent: "center",
  },
  cardTitle: {
    fontSize: 12,
    fontWeight: "800",
    color: doctorPalette.inkSecondary,
    flex: 1,
  },
  cardMeta: {
    fontSize: 11,
    fontWeight: "700",
    color: doctorPalette.muted,
  },
  loadingText: {
    fontSize: 13,
    fontWeight: "600",
    color: doctorPalette.muted,
  },
  legend: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 10,
  },
  legendChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
  },
  legendDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  legendText: {
    fontSize: 11,
    fontWeight: "700",
    color: doctorPalette.inkSecondary,
  },
  metricRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 8,
    borderTopWidth: 1,
    borderTopColor: doctorPalette.borderSubtle,
    paddingTop: 12,
  },
  metricCol: {
    flex: 1,
    alignItems: "center",
    gap: 3,
  },
  metricValue: {
    fontSize: 15,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  metricLabel: {
    fontSize: 11,
    fontWeight: "600",
    color: doctorPalette.muted,
  },
});