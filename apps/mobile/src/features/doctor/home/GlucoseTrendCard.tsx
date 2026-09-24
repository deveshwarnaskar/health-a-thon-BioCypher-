import React, { useMemo, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { doctorPalette, doctorRadii, doctorSoftShadow } from "../doctorDesign";
import { SectionHeader, SegmentControl, MiniSparkBars, HomeInlineState } from "./DoctorHomeBits";
import type { TrendGranularity } from "../useCohortClinicalSummary";

export type TrendSeries = { label: string; value: number }[];

function bucketDaily(series: TrendSeries, groupSize: number): TrendSeries {
  const buckets: TrendSeries = [];
  for (let i = 0; i < series.length; i += groupSize) {
    const chunk = series.slice(i, i + groupSize);
    const avg = chunk.reduce((sum, p) => sum + p.value, 0) / chunk.length;
    buckets.push({
      label: `wk${Math.floor(i / groupSize) + 1}`,
      value: Math.round(avg),
    });
  }
  return buckets;
}

export function GlucoseTrendCard({
  dailySeries,
  mean7d,
  mean30d,
  mean90d,
  previous7d,
  isLoading,
  hasData,
}: {
  dailySeries: TrendSeries;
  mean7d: number | null;
  mean30d: number | null;
  mean90d: number | null;
  previous7d: number | null;
  isLoading: boolean;
  hasData: boolean;
}) {
  const [granularity, setGranularity] = useState<TrendGranularity>("daily");

  const points = useMemo(() => {
    if (granularity === "daily") return dailySeries;
    if (granularity === "weekly") return bucketDaily(dailySeries, 7);
    return bucketDaily(dailySeries, 30);
  }, [dailySeries, granularity]);

  const headlineMean = granularity === "daily" ? mean7d : granularity === "weekly" ? mean30d : mean90d;
  const headlineLabel = granularity === "daily" ? "7-day cohort average" : granularity === "weekly" ? "30-day cohort average" : "90-day cohort average";

  const delta = previous7d === null ? null : (mean7d ?? 0) - previous7d;
  const direction =
    delta === null || Math.abs(delta) < 1
      ? ("stable" as const)
      : delta > 0
        ? ("deteriorating" as const)
        : ("improving" as const);

  return (
    <View style={styles.section}>
      <SectionHeader title="Glucose Trend" viewAllLabel="Open telemetry" onViewAll={undefined} />
      <View style={styles.card}>
        <SegmentControl
          options={[
            { key: "daily", label: "Daily" },
            { key: "weekly", label: "Weekly" },
            { key: "monthly", label: "Monthly" },
          ]}
          selected={granularity}
          onSelect={(key) => setGranularity(key as TrendGranularity)}
          accessibilityHint={(o) => `Show cohort glucose ${o.label.toLowerCase()} trend`}
        />
        {isLoading ? (
          <Text style={styles.loadingText} allowFontScaling>
            Loading trend…
          </Text>
        ) : hasData ? (
          <>
            <View style={styles.trendHeader}>
              <View>
                <Text style={styles.bigValue} allowFontScaling>
                  {headlineMean === null ? "—" : `${headlineMean} mg/dL`}
                </Text>
                <Text style={styles.bigLabel} allowFontScaling>
                  {headlineLabel}
                </Text>
              </View>
              <View style={styles.deltaWrap}>
                <DeltaChip delta={delta} direction={direction} />
              </View>
            </View>
            <View style={styles.sparkWrap}>
              <MiniSparkBars values={points} />
              <View style={styles.axisRow}>
                <Text style={styles.axisLabel} allowFontScaling>
                  Oldest
                </Text>
                <Text style={styles.axisLabel} allowFontScaling>
                  Latest
                </Text>
              </View>
            </View>
          </>
        ) : (
          <HomeInlineState
            icon="analytics-outline"
            title="Trend unavailable"
            message="Not enough confirmed readings to chart a cohort glucose trend yet. It will appear as observations are received."
          />
        )}
      </View>
    </View>
  );
}

function DeltaChip({ delta, direction }: { delta: number | null; direction: "improving" | "stable" | "deteriorating" }) {
  const tint =
    delta === null || direction === "stable"
      ? doctorPalette.muted
      : direction === "improving"
        ? "#15803D"
        : doctorPalette.criticalText;
  const glyph: React.ComponentProps<typeof Ionicons>["name"] =
    delta === null || Math.abs(delta) < 1 ? "remove" : delta > 0 ? "arrow-up" : "arrow-down";
  return (
    <View style={styles.deltaChip} accessible accessibilityRole="text" accessibilityLabel={delta === null ? "Trend stable" : `7-day change ${Math.round(delta)} mg/dL`}>
      <Ionicons name={glyph} size={13} color={tint} />
      <Text style={[styles.deltaChipText, { color: tint }]} allowFontScaling>
        {delta === null ? "—" : `${delta > 0 ? "+" : ""}${Math.round(delta)}`}
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
  loadingText: {
    fontSize: 13,
    fontWeight: "600",
    color: doctorPalette.muted,
  },
  trendHeader: {
    flexDirection: "row",
    alignItems: "flex-end",
    justifyContent: "space-between",
  },
  bigValue: {
    fontSize: 28,
    lineHeight: 31,
    fontWeight: "800",
    color: doctorPalette.ink,
    letterSpacing: -0.4,
  },
  bigLabel: {
    fontSize: 12,
    fontWeight: "600",
    color: doctorPalette.muted,
    marginTop: 2,
  },
  deltaWrap: {
    alignItems: "flex-end",
  },
  deltaChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    backgroundColor: doctorPalette.surfaceSoft,
    borderRadius: doctorRadii.pill,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  deltaChipText: {
    fontSize: 12,
    fontWeight: "800",
  },
  sparkWrap: {
    gap: 4,
  },
  axisRow: {
    flexDirection: "row",
    justifyContent: "space-between",
  },
  axisLabel: {
    fontSize: 10,
    fontWeight: "600",
    color: doctorPalette.quiet,
  },
});