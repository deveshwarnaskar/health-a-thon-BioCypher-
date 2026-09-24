import React from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { colors, radii, spacing, typography } from "../../../theming/tokens";
import type { TimelineEvent } from "../types";
import { SyncStatusBadge } from "../../../components/primitives/SyncStatusBadge";

import { Ionicons } from "@expo/vector-icons";

export type TimelineItemRowProps = {
  event: TimelineEvent;
  onPress?: (event: TimelineEvent) => void;
};

function EventNodeIcon({ type }: { type: TimelineEvent["type"] }) {
  switch (type) {
    case "glucose":
      return <Ionicons name="water" size={14} color="#DC2626" />;
    case "meal":
      return <Ionicons name="restaurant" size={14} color="#D97706" />;
    case "medication":
      return <Ionicons name="medkit" size={14} color="#2563EB" />;
    case "task":
      return <Ionicons name="checkbox" size={14} color="#7C3AED" />;
    case "document":
      return <Ionicons name="document-text" size={14} color="#0D9488" />;
    default:
      return <Ionicons name="pulse" size={14} color="#64748B" />;
  }
}

function getNodeBg(type: TimelineEvent["type"]): string {
  switch (type) {
    case "glucose":
      return "#FEF2F2";
    case "meal":
      return "#FFFBEB";
    case "medication":
      return "#EFF6FF";
    case "task":
      return "#F5F3FF";
    case "document":
      return "#F0FDFA";
    default:
      return "#F8FAFC";
  }
}

export function TimelineItemRow({ event, onPress }: TimelineItemRowProps) {
  const timeStr = event.timestamp
    ? new Date(event.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : "";

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
        <View style={[styles.node, { backgroundColor: getNodeBg(event.type) }]}>
          <EventNodeIcon type={event.type} />
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
    width: 62,
    paddingTop: 6,
    alignItems: "flex-end",
    marginRight: spacing.xs,
  },
  timeText: {
    fontSize: 12,
    color: "#64748B",
    fontWeight: "600",
  },
  nodeColumn: {
    alignItems: "center",
    marginRight: spacing.sm,
  },
  node: {
    width: 30,
    height: 30,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 1,
  },
  connector: {
    width: 2,
    flex: 1,
    minHeight: 28,
    backgroundColor: "#E2E8F0",
    marginTop: -2,
    marginBottom: -2,
  },
  card: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    padding: spacing.sm + 2,
    marginBottom: spacing.xs,
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 10,
    elevation: 2,
  },
  cardTop: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 2,
  },
  title: {
    fontSize: 14,
    fontWeight: "700",
    color: "#0F172A",
    flex: 1,
  },
  subtitle: {
    fontSize: 12,
    color: "#64748B",
    lineHeight: 16,
  },
});
