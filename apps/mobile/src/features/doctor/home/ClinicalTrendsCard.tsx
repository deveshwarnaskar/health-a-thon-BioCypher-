import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { doctorPalette, doctorSoftShadow } from "../doctorDesign";
import { SectionHeader, HomeInlineState } from "./DoctorHomeBits";
import type { TrendComparisons } from "../../../services/clinical/cohortClinicalAnalysis";

function directionIcon(direction: TrendComparisons["tir"]["direction"]) {
  if (direction === "stable") return "remove";
  return direction === "improving" ? "arrow-up" : "arrow-down";
}

function formatDelta(delta: number | null): string {
  if (delta === null) return "—";
  return `${delta > 0 ? "+" : ""}${delta}`;
}

export function ClinicalTrendsCard({
  trend,
  isLoading,
  hasData,
  onViewAll,
}: {
  trend: TrendComparisons;
  isLoading: boolean;
  hasData: boolean;
  onViewAll?: () => void;
}) {
  return (
    <View style={styles.section}>
      <SectionHeader title="Clinical Trends" viewAllLabel="Open AI Review" onViewAll={onViewAll} />
      <View style={styles.card}>
        {isLoading ? (
          <Text style={styles.loadingText} allowFontScaling>
            Comparing periods…
          </Text>
        ) : !hasData ? (
          <HomeInlineState
            icon="trending-up-outline"
            title="Trends will appear with data"
            message="We compare the current period against the previous period. No connected data exists yet."
          />
        ) : (
          <>
            <TrendRow
              label="Time in Range"
              current={trend.tir.current === null ? "—" : `${trend.tir.current}%`}
              icon="water"
              color="#10B981"
              delta={formatDelta(trend.tir.delta)}
              direction={trend.tir.direction}
            />
            <TrendRow
              label="Mean Glucose"
              current={trend.mean.current === null ? "—" : `${trend.mean.current} mg/dL`}
              icon="speedometer-outline"
              color={doctorPalette.primary}
              delta={formatDelta(trend.mean.delta)}
              direction={trend.mean.direction}
            />
            <TrendRow
              label="GMI"
              current={trend.gmi.current === null ? "—" : `${trend.gmi.current}%`}
              icon="golf-outline"
              color="#7C3AED"
              delta={formatDelta(trend.gmi.delta)}
              direction={trend.gmi.direction}
            />
            <TrendRow
              label="Time Below Range"
              current={trend.tbr.current === null ? "—" : `${trend.tbr.current}%`}
              icon="warning-outline"
              color="#EF4444"
              delta={formatDelta(trend.tbr.delta)}
              direction={trend.tbr.direction}
            />
            <TrendRow
              label="CV"
              current={trend.cv.current === null ? "—" : `${trend.cv.current}%`}
              icon="stats-chart-outline"
              color="#F59E0B"
              delta={formatDelta(trend.cv.delta)}
              direction={trend.cv.direction}
            />
            <Text style={styles.caption} allowFontScaling>
              Current period vs previous period of equal length
            </Text>
          </>
        )}
      </View>
    </View>
  );
}

function TrendRow({
  label,
  current,
  icon,
  color,
  delta,
  direction,
}: {
  label: string;
  current: string;
  icon: React.ComponentProps<typeof Ionicons>["name"];
  color: string;
  delta: string;
  direction: TrendComparisons["tir"]["direction"];
}) {
  const good = direction === "improving";
  const tint = direction === "stable" ? doctorPalette.muted : good ? "#15803D" : doctorPalette.criticalText;
  return (
    <View style={styles.row}>
      <View style={[styles.rowIcon, { backgroundColor: `${color}1A` }]}>
        <Ionicons name={icon} size={15} color={color} />
      </View>
      <Text style={styles.rowLabel} allowFontScaling numberOfLines={1}>
        {label}
      </Text>
      <Text style={styles.rowValue} allowFontScaling>
        {current}
      </Text>
      <View style={styles.delta} accessible accessibilityRole="text" accessibilityLabel={`${label} change ${delta}`}>
        <Ionicons name={directionIcon(direction)} size={12} color={tint} />
        <Text style={[styles.deltaText, { color: tint }]} allowFontScaling>
          {delta}
        </Text>
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
    gap: 4,
    ...doctorSoftShadow,
  },
  loadingText: {
    fontSize: 13,
    fontWeight: "600",
    color: doctorPalette.muted,
    paddingVertical: 8,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingVertical: 9,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: doctorPalette.borderSubtle,
  },
  rowIcon: {
    width: 30,
    height: 30,
    borderRadius: 15,
    alignItems: "center",
    justifyContent: "center",
  },
  rowLabel: {
    fontSize: 13,
    fontWeight: "700",
    color: doctorPalette.inkSecondary,
    flex: 1,
  },
  rowValue: {
    fontSize: 14,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  delta: {
    flexDirection: "row",
    alignItems: "center",
    gap: 3,
    minWidth: 52,
    justifyContent: "flex-end",
  },
  deltaText: {
    fontSize: 12,
    fontWeight: "800",
  },
  caption: {
    fontSize: 11,
    fontWeight: "600",
    color: doctorPalette.muted,
    paddingTop: 8,
    textAlign: "center",
  },
});