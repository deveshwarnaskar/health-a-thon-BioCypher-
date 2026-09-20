import React from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { colors, radii, spacing, typography } from "../../../theming/tokens";
import type { TimelineEvent } from "../types";
import { SyncStatusBadge } from "../../../components/primitives/SyncStatusBadge";

export type TimelineItemRowProps = {
  event: TimelineEvent;
  onPress?: (event: TimelineEvent) => void;
};

function getEventIcon(type: TimelineEvent["type"]): string {
  switch (type) {
    case "glucose":
      return "🩸";
    case "meal":
      return "🍲";
    case "medication":
      return "💊";
    case "task":
      return "✓";
  }
}

export function TimelineItemRow({ event, onPress }: TimelineItemRowProps) {
  const timeStr = event.timestamp
    ? new Date(event.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : "";

  const icon = getEventIcon(event.type);
  const isSavedLocally = event.status === "SAVED_LOCALLY" || event.status === "PENDING";

  return (
    <TouchableOpacity
      style={styles.container}
      onPress={() => onPress?.(event)}
      activeOpacity={0.7}
      accessibilityRole="button"
      accessibilityLabel={`${event.title}, ${event.subtitle}, at ${timeStr}`}
    >
      <View style={styles.timeColumn}>
        <Text style={styles.timeText} allowFontScaling>
          {timeStr}
        </Text>
      </View>

      <View style={styles.nodeColumn}>
        <View style={styles.node}>
          <Text style={styles.icon} allowFontScaling>
            {icon}
          </Text>
        </View>
        <View style={styles.connector} />
      </View>

      <View style={styles.card}>
        <View style={styles.cardTop}>
          <Text style={styles.title} allowFontScaling numberOfLines={1}>
            {event.title}
          </Text>
          {isSavedLocally ? (
            <SyncStatusBadge status="SAVED_LOCALLY" />
          ) : null}
        </View>
        <Text style={styles.subtitle} allowFontScaling numberOfLines={2}>
          {event.subtitle}
        </Text>
      </View>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: "row",
    alignItems: "flex-start",
    marginBottom: spacing.xs,
  },
  timeColumn: {
    width: 60,
    paddingTop: 4,
    alignItems: "flex-end",
    marginRight: spacing.xs,
  },
  timeText: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    fontWeight: typography.weight.medium,
  },
  nodeColumn: {
    alignItems: "center",
    marginRight: spacing.sm,
  },
  node: {
    width: 28,
    height: 28,
    borderRadius: radii.pill,
    backgroundColor: "#F0F7F9",
    borderWidth: 1.5,
    borderColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
    zIndex: 1,
  },
  icon: {
    fontSize: 13,
  },
  connector: {
    width: 2,
    flex: 1,
    minHeight: 24,
    backgroundColor: colors.border,
    marginTop: -2,
    marginBottom: -2,
  },
  card: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.sm,
    marginBottom: spacing.xs,
  },
  cardTop: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 2,
  },
  title: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
    flex: 1,
  },
  subtitle: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
  },
});
