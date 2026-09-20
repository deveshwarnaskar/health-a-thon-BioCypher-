import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { colors, radii, spacing, typography } from "../../../theming/tokens";

export type TodayItemStatus = "completed" | "pending" | "due";

export type TodayItem = {
  id: string;
  label: string;
  status: TodayItemStatus;
  statusLabel?: string;
  time?: string;
};

export type TodaySummaryCardProps = {
  items: TodayItem[];
};

export function TodaySummaryCard({ items }: TodaySummaryCardProps) {
  const pendingCount = items.filter((i) => i.status !== "completed").length;

  return (
    <View style={styles.container} accessibilityRole="summary">
      <View style={styles.headerRow}>
        <View>
          <Text style={styles.kicker} allowFontScaling>
            TODAY
          </Text>
          <Text style={styles.title} allowFontScaling>
            {pendingCount === 0
              ? "All caught up for today"
              : `${pendingCount} ${pendingCount === 1 ? "item needs" : "things need"} your attention`}
          </Text>
        </View>
        <View
          style={[
            styles.countPill,
            pendingCount === 0 ? styles.countPillComplete : styles.countPillAttention,
          ]}
        >
          <Text
            style={[
              styles.countPillText,
              pendingCount === 0 ? styles.countPillTextComplete : styles.countPillTextAttention,
            ]}
            allowFontScaling
          >
            {pendingCount === 0 ? "✓ Done" : `${pendingCount} pending`}
          </Text>
        </View>
      </View>

      <View style={styles.divider} />

      <View style={styles.list}>
        {items.map((item) => {
          const isDone = item.status === "completed";
          return (
            <View
              key={item.id}
              style={styles.itemRow}
              accessible
              accessibilityLabel={`${item.label}, ${isDone ? "completed" : "needs attention"}`}
            >
              <Text style={[styles.itemLabel, isDone && styles.itemLabelDone]} allowFontScaling>
                {item.label}
              </Text>
              <View style={styles.itemStatusContainer}>
                {item.time ? (
                  <Text style={styles.itemTime} allowFontScaling>
                    {item.time}
                  </Text>
                ) : null}
                <View
                  style={[
                    styles.statusIndicator,
                    isDone ? styles.statusIndicatorDone : styles.statusIndicatorPending,
                  ]}
                >
                  <Text
                    style={[
                      styles.indicatorIcon,
                      isDone ? styles.indicatorIconDone : styles.indicatorIconPending,
                    ]}
                    allowFontScaling
                  >
                    {isDone ? "✓" : "○"}
                  </Text>
                </View>
              </View>
            </View>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.surface,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 3,
    elevation: 2,
  },
  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
  },
  kicker: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.weight.bold,
    letterSpacing: 1.2,
    color: colors.primary,
    marginBottom: 2,
  },
  title: {
    fontSize: typography.fontSize.body,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
  },
  countPill: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderRadius: radii.pill,
  },
  countPillAttention: {
    backgroundColor: "#FDF2E9",
  },
  countPillComplete: {
    backgroundColor: "#E8F8F5",
  },
  countPillText: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.weight.semibold,
  },
  countPillTextAttention: {
    color: colors.assistive,
  },
  countPillTextComplete: {
    color: colors.leafGreen,
  },
  divider: {
    height: 1,
    backgroundColor: colors.border,
    marginVertical: spacing.sm,
  },
  list: {
    gap: spacing.sm,
  },
  itemRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  itemLabel: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: typography.weight.medium,
    color: colors.textPrimary,
  },
  itemLabelDone: {
    color: colors.textSecondary,
    textDecorationLine: "line-through",
  },
  itemStatusContainer: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
  },
  itemTime: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
  },
  statusIndicator: {
    width: 24,
    height: 24,
    borderRadius: radii.pill,
    alignItems: "center",
    justifyContent: "center",
  },
  statusIndicatorPending: {
    borderWidth: 1.5,
    borderColor: colors.assistive,
    backgroundColor: "transparent",
  },
  statusIndicatorDone: {
    backgroundColor: colors.leafGreen,
  },
  indicatorIcon: {
    fontSize: 12,
    fontWeight: "bold",
  },
  indicatorIconPending: {
    color: colors.assistive,
  },
  indicatorIconDone: {
    color: colors.textOnPrimary,
  },
});
