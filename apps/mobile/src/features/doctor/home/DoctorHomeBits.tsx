import React from "react";
import { Pressable, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { touchTarget } from "../../../theming/tokens";
import { doctorPalette, doctorRadii, doctorSoftShadow } from "../doctorDesign";
import type { TrendDirection } from "../../../services/clinical/cohortClinicalAnalysis";

export type SegmentOption = { key: string; label: string };

export function SectionHeader({
  title,
  onViewAll,
  viewAllLabel = "View all",
  accessibilityLabel,
}: {
  title: string;
  onViewAll?: () => void;
  viewAllLabel?: string;
  accessibilityLabel?: string;
}) {
  return (
    <View style={styles.sectionHeaderRow}>
      <Text style={styles.sectionTitle} allowFontScaling>
        {title}
      </Text>
      {onViewAll ? (
        <TouchableOpacity
          onPress={onViewAll}
          accessibilityRole="button"
          accessibilityLabel={accessibilityLabel ?? `View all ${title}`}
          hitSlop={touchTarget.hitSlop}
        >
          <Text style={styles.viewAllText} allowFontScaling>
            {viewAllLabel} →
          </Text>
        </TouchableOpacity>
      ) : null}
    </View>
  );
}

export function SegmentControl({
  options,
  selected,
  onSelect,
  accessibilityHint,
}: {
  options: SegmentOption[];
  selected: string;
  onSelect: (key: string) => void;
  accessibilityHint?: (option: SegmentOption) => string;
}) {
  return (
    <View style={styles.segmentRow} accessibilityRole="tablist">
      {options.map((option) => {
        const active = option.key === selected;
        return (
          <Pressable
            key={option.key}
            style={[styles.segment, active ? styles.segmentActive : null]}
            onPress={() => onSelect(option.key)}
            accessibilityRole="tab"
            accessibilityLabel={option.label}
            accessibilityHint={accessibilityHint?.(option)}
            accessibilityState={{ selected: active }}
          >
            <Text
              style={[styles.segmentText, active ? styles.segmentTextActive : null]}
              allowFontScaling
            >
              {option.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

export function MetricTile({
  icon,
  value,
  label,
  subLabel,
  badge,
  dotColor,
  valueColor,
  accessibilityLabel,
}: {
  icon: React.ComponentProps<typeof Ionicons>["name"];
  value: string;
  label: string;
  subLabel?: string;
  badge?: string;
  dotColor?: string;
  valueColor?: string;
  accessibilityLabel?: string;
}) {
  return (
    <View
      style={styles.metricTile}
      accessible
      accessibilityRole="text"
      accessibilityLabel={accessibilityLabel ?? `${label}: ${value}${subLabel ? `, ${subLabel}` : ""}`}
    >
      <View style={styles.metricTopRow}>
        <View style={styles.metricIconWrap}>
          <Ionicons name={icon} size={16} color={doctorPalette.primary} />
        </View>
        <View style={styles.metricTopRight}>
          {badge ? (
            <View style={[styles.metricBadge, dotColor ? { backgroundColor: `${dotColor}20` } : null]}>
              <Text style={[styles.metricBadgeText, dotColor ? { color: dotColor } : null]} allowFontScaling numberOfLines={1}>
                {badge}
              </Text>
            </View>
          ) : dotColor ? (
            <View style={[styles.metricDot, { backgroundColor: dotColor }]} />
          ) : null}
        </View>
      </View>
      <Text style={[styles.metricValue, valueColor ? { color: valueColor } : null]} allowFontScaling numberOfLines={1}>
        {value}
      </Text>
      <View style={styles.metricLabelCol}>
        <Text style={styles.metricLabel} allowFontScaling numberOfLines={1}>
          {label}
        </Text>
        {subLabel ? (
          <Text style={styles.metricSubLabel} allowFontScaling numberOfLines={1}>
            {subLabel}
          </Text>
        ) : null}
      </View>
    </View>
  );
}

/** Horizontal TIR / TAR / TBR stacked range bar (ADA/EASD 70–180 mg/dL). */
export function RangeBar({
  belowPct,
  inRangePct,
  abovePct,
}: {
  belowPct: number;
  inRangePct: number;
  abovePct: number;
}) {
  const total = belowPct + inRangePct + abovePct;
  const hasData = total > 0;
  return (
    <View style={styles.rangeBarTrack} accessibilityRole="progressbar" accessibilityValue={{ min: 0, max: 100, now: Math.round(inRangePct) }}>
      {hasData ? (
        <>
          {belowPct > 0 ? (
            <View style={[styles.rangeBarSegment, { flex: belowPct, backgroundColor: "#EF4444" }]} />
          ) : null}
          {inRangePct > 0 ? (
            <View style={[styles.rangeBarSegment, { flex: inRangePct, backgroundColor: "#10B981" }]} />
          ) : null}
          {abovePct > 0 ? (
            <View style={[styles.rangeBarSegment, { flex: abovePct, backgroundColor: "#F59E0B" }]} />
          ) : null}
        </>
      ) : (
        <View style={styles.rangeBarEmpty}>
          <Text style={styles.rangeBarEmptyText} allowFontScaling>
            No data
          </Text>
        </View>
      )}
    </View>
  );
}

/** Lightweight, dependency-free daily-average bar sparkline. */
export function MiniSparkBars({
  values,
  height = 56,
  emptyLabel = "Insufficient data for this period",
}: {
  values: { value: number }[];
  height?: number;
  emptyLabel?: string;
}) {
  if (values.length === 0) {
    return (
      <View style={[styles.sparkEmpty, { height }]}>
        <Ionicons name="analytics-outline" size={18} color={doctorPalette.quiet} />
        <Text style={styles.sparkEmptyText} allowFontScaling>
          {emptyLabel}
        </Text>
      </View>
    );
  }
  const max = Math.max(...values.map((v) => v.value), 1);
  const barCount = Math.min(values.length, 18);
  const stepped = values.slice(-barCount);
  return (
    <View style={styles.sparkRow} accessible accessibilityRole="image" accessibilityLabel="Cohort average glucose trend">
      {stepped.map((point, index) => {
        const isLatest = index === stepped.length - 1;
        const barHeight = Math.max(6, (point.value / max) * height);
        return (
          <View key={`${index}-${point.value}`} style={styles.sparkBarColumn}>
            <View
              style={[
                styles.sparkBar,
                {
                  height: barHeight,
                  backgroundColor: isLatest ? doctorPalette.primary : "#C6D8FF",
                },
              ]}
            />
          </View>
        );
      })}
    </View>
  );
}

export function DeltaPill({
  delta,
  unit,
  direction,
  accessibilityLabel,
}: {
  delta: number | null;
  unit: string;
  direction?: TrendDirection;
  accessibilityLabel?: string;
}) {
  let icon: React.ComponentProps<typeof Ionicons>["name"] = "remove";
  let tint: string = doctorPalette.muted;
  if (delta !== null && delta !== undefined) {
    if (delta > 0.05) icon = "arrow-up";
    else if (delta < -0.05) icon = "arrow-down";
    else icon = "remove";
    const improving =
      direction === "improving" || (direction === undefined && delta <= 0);
    tint =
      Math.abs(delta) <= 0.05
        ? doctorPalette.muted
        : improving
          ? "#15803D"
          : doctorPalette.criticalText;
  }
  return (
    <View style={styles.deltaPill} accessible accessibilityRole="text" accessibilityLabel={accessibilityLabel}>
      <Ionicons name={icon} size={13} color={tint} />
      <Text style={[styles.deltaText, { color: tint }]} allowFontScaling>
        {delta === null || delta === undefined ? "—" : `${delta > 0 ? "+" : ""}${delta} ${unit}`}
      </Text>
    </View>
  );
}

export function HomeCard({ children, style }: { children: React.ReactNode; style?: object }) {
  return <View style={[styles.card, style]}>{children}</View>;
}

export function HomeInlineState({
  icon,
  title,
  message,
}: {
  icon: React.ComponentProps<typeof Ionicons>["name"];
  title: string;
  message: string;
}) {
  return (
    <View style={styles.inlineState} accessible accessibilityRole="summary" accessibilityLabel={`${title}. ${message}`}>
      <View style={styles.inlineIconWrap}>
        <Ionicons name={icon} size={20} color={doctorPalette.quiet} />
      </View>
      <Text style={styles.inlineTitle} allowFontScaling>
        {title}
      </Text>
      <Text style={styles.inlineMessage} allowFontScaling>
        {message}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  sectionHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: "800",
    color: doctorPalette.ink,
    letterSpacing: -0.2,
  },
  viewAllText: {
    fontSize: 13,
    fontWeight: "700",
    color: doctorPalette.primary,
  },
  segmentRow: {
    flexDirection: "row",
    backgroundColor: doctorPalette.appBackground,
    borderRadius: doctorRadii.pill,
    padding: 3,
    gap: 4,
  },
  segment: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    minHeight: 34,
    borderRadius: doctorRadii.pill,
    paddingHorizontal: 14,
  },
  segmentActive: {
    backgroundColor: doctorPalette.surfaceLime,
  },
  segmentText: {
    fontSize: 12,
    fontWeight: "700",
    color: doctorPalette.muted,
  },
  segmentTextActive: {
    color: doctorPalette.ink,
    fontWeight: "800",
  },
  metricTile: {
    flexGrow: 1,
    flexBasis: "47%",
    minWidth: 140,
    backgroundColor: doctorPalette.surface,
    borderRadius: doctorRadii.lg,
    borderWidth: 1,
    borderColor: doctorPalette.borderSubtle,
    padding: 14,
    gap: 8,
    ...doctorSoftShadow,
  },
  metricTopRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  metricIconWrap: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: doctorPalette.surfaceBlue,
    alignItems: "center",
    justifyContent: "center",
  },
  metricTopRight: {
    flexDirection: "row",
    alignItems: "center",
  },
  metricDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  metricBadge: {
    borderRadius: doctorRadii.pill,
    paddingHorizontal: 7,
    paddingVertical: 3,
  },
  metricBadgeText: {
    fontSize: 10,
    fontWeight: "800",
  },
  metricValue: {
    fontSize: 26,
    lineHeight: 30,
    fontWeight: "800",
    color: doctorPalette.ink,
    letterSpacing: -0.4,
  },
  metricLabelCol: {
    gap: 2,
  },
  metricLabel: {
    fontSize: 12,
    fontWeight: "700",
    color: doctorPalette.inkSecondary,
  },
  metricSubLabel: {
    fontSize: 10,
    fontWeight: "600",
    color: doctorPalette.muted,
  },
  rangeBarTrack: {
    flexDirection: "row",
    height: 12,
    borderRadius: 6,
    overflow: "hidden",
    backgroundColor: doctorPalette.surfaceSoft,
  },
  rangeBarSegment: {
    height: "100%",
  },
  rangeBarEmpty: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  rangeBarEmptyText: {
    fontSize: 10,
    fontWeight: "700",
    color: doctorPalette.quiet,
  },
  sparkEmpty: {
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    borderRadius: doctorRadii.md,
    backgroundColor: doctorPalette.surfaceSoft,
  },
  sparkEmptyText: {
    fontSize: 11,
    fontWeight: "600",
    color: doctorPalette.quiet,
  },
  sparkRow: {
    flexDirection: "row",
    alignItems: "flex-end",
    gap: 4,
    height: 56,
    paddingHorizontal: 2,
  },
  sparkBarColumn: {
    flex: 1,
    alignItems: "stretch",
    justifyContent: "flex-end",
  },
  sparkBar: {
    width: "100%",
    borderTopLeftRadius: 4,
    borderTopRightRadius: 4,
    minHeight: 6,
  },
  deltaPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    backgroundColor: doctorPalette.surfaceSoft,
    borderRadius: doctorRadii.pill,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  deltaText: {
    fontSize: 12,
    fontWeight: "800",
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
  inlineState: {
    alignItems: "center",
    gap: 6,
    paddingVertical: 14,
    paddingHorizontal: 10,
    borderRadius: doctorRadii.lg,
    backgroundColor: doctorPalette.surfaceSoft,
    borderWidth: 1,
    borderColor: doctorPalette.borderSubtle,
  },
  inlineIconWrap: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: doctorPalette.surface,
    alignItems: "center",
    justifyContent: "center",
  },
  inlineTitle: {
    fontSize: 13,
    fontWeight: "800",
    color: doctorPalette.ink,
    textAlign: "center",
  },
  inlineMessage: {
    fontSize: 12,
    lineHeight: 17,
    color: doctorPalette.muted,
    textAlign: "center",
  },
});

export const homeSectionSpacing = 20;
export const homeSectionGroup = 12;