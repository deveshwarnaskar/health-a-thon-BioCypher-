import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
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
        <View style={styles.headerLeft}>
          <Text style={styles.kicker} allowFontScaling>
            TODAY&apos;S CARE
          </Text>
          <Text style={styles.title} allowFontScaling>
            {pendingCount === 0
              ? "All caught up for today"
              : `${pendingCount} ${pendingCount === 1 ? "item needs" : "things need"} attention`}
          </Text>
        </View>
        <View
          style={[
            styles.countPill,
            pendingCount === 0 ? styles.countPillComplete : styles.countPillAttention,
          ]}
        >
          {pendingCount === 0 ? (
            <Ionicons name="checkmark-circle" size={13} color="#065F46" style={{ marginRight: 3 }} />
          ) : (
            <Ionicons name="time-outline" size={13} color="#78350F" style={{ marginRight: 3 }} />
          )}
          <Text
            style={[
              styles.countPillText,
              pendingCount === 0 ? styles.countPillTextComplete : styles.countPillTextAttention,
            ]}
            allowFontScaling
          >
            {pendingCount === 0 ? "Complete" : `${pendingCount} pending`}
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
                  <Ionicons
                    name={isDone ? "checkmark" : "ellipse-outline"}
                    size={13}
                    color={isDone ? "#FFFFFF" : "#F59E0B"}
                  />
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
    backgroundColor: "#FFFFFF",
    borderRadius: 20,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    padding: spacing.md,
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.04,
    shadowRadius: 8,
    elevation: 2,
  },
  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
  },
  headerLeft: {
    flex: 1,
    paddingRight: spacing.xs,
  },
  kicker: {
    fontSize: 10,
    fontWeight: "700",
    letterSpacing: 1.1,
    color: "#0D9488",
    marginBottom: 3,
  },
  title: {
    fontSize: 16,
    lineHeight: 22,
    fontWeight: "800",
    color: "#0F172A",
    letterSpacing: -0.2,
  },
  countPill: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: radii.pill,
    borderWidth: 1,
  },
  countPillAttention: {
    backgroundColor: "#FFFBEB",
    borderColor: "#FEF3C7",
  },
  countPillComplete: {
    backgroundColor: "#ECFDF5",
    borderColor: "#D1FAE5",
  },
  countPillText: {
    fontSize: 11,
    fontWeight: "700",
  },
  countPillTextAttention: {
    color: "#B45309",
  },
  countPillTextComplete: {
    color: "#059669",
  },
  divider: {
    height: 1,
    backgroundColor: "#F1F5F9",
    marginVertical: spacing.sm,
  },
  list: {
    gap: 8,
  },
  itemRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: 3,
  },
  itemLabel: {
    flex: 1,
    fontSize: 13,
    fontWeight: "600",
    color: "#1E293B",
    paddingRight: spacing.xs,
  },
  itemLabelDone: {
    color: "#94A3B8",
    textDecorationLine: "line-through",
  },
  itemStatusContainer: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  itemTime: {
    fontSize: 11,
    color: "#64748B",
    fontWeight: "500",
  },
  statusIndicator: {
    width: 22,
    height: 22,
    borderRadius: 11,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
  },
  statusIndicatorDone: {
    backgroundColor: "#10B981",
    borderColor: "#10B981",
  },
  statusIndicatorPending: {
    backgroundColor: "#FFFBEB",
    borderColor: "#FCD34D",
  },
});
