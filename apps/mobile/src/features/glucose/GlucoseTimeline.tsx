import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Badge } from "../../components/primitives/Badge";
import { LoadingState } from "../../components/primitives/LoadingState";
import { EmptyState } from "../../components/primitives/EmptyState";
import { ErrorState } from "../../components/primitives/ErrorState";
import { colors, radii, spacing } from "../../theming/tokens";
import {
  READING_TAG_LABELS,
  type PatientGlucoseObservation,
  type ReadingTag,
} from "./types";
import { evaluateGlucose } from "./glucoseRanges";

/**
 * Consistent clinical palettes for the logbook (anchored to design tokens).
 */
const palette = {
  bold: "#475569",
  muted: "#64748B",
  ink: "#0F172A",
  border: "rgba(15, 23, 42, 0.07)",
  hairline: "#EEF2F7",
} as const;

export type GlucoseTimelineProps = {
  readings?: PatientGlucoseObservation[];
  items?: PatientGlucoseObservation[];
  isLoading?: boolean;
  isError?: boolean;
  onRetry?: () => void;
  testID?: string;
};

function formatTimestamp(isoString: string): string {
  try {
    const date = new Date(isoString);
    if (Number.isNaN(date.getTime())) return isoString;
    return date.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return isoString;
  }
}

export function GlucoseTimeline({
  readings,
  items,
  isLoading = false,
  isError = false,
  onRetry,
  testID,
}: GlucoseTimelineProps) {
  const data = readings ?? items ?? [];

  if (isLoading) {
    return (
      <View testID="glucose-timeline-loading">
        <LoadingState label="Loading glucose history…" />
      </View>
    );
  }

  if (isError) {
    return (
      <View testID="glucose-timeline-error">
        <ErrorState
          title="Could not load readings"
          message="Unable to connect to your clinical record. Please try again."
          onRetry={onRetry}
        />
      </View>
    );
  }

  if (data.length === 0) {
    return (
      <View testID="glucose-timeline-empty">
        <EmptyState
          title="No glucose readings"
          message="Your recorded blood glucose observations will appear here in chronological order."
        />
      </View>
    );
  }

  // Sort descending by taken_at timestamp
  const sorted = [...data].sort((a, b) => {
    const timeA = new Date(a.taken_at).getTime() || 0;
    const timeB = new Date(b.taken_at).getTime() || 0;
    return timeB - timeA;
  });

  return (
    <View style={styles.container} testID={testID}>
      {/* Section Header */}
      <View style={styles.headerRow}>
        <View style={styles.headerLeft}>
          <Text style={styles.title} allowFontScaling>
            Recent Readings
          </Text>
          <Text style={styles.subtitle} allowFontScaling>
            Chronological log of verified clinical readings
          </Text>
        </View>
        <View style={styles.countBadge}>
          <Text style={styles.countBadgeText} allowFontScaling>
            {sorted.length} {sorted.length === 1 ? "entry" : "entries"}
          </Text>
        </View>
      </View>

      {/* Observation Cards */}
      <View style={styles.list}>
        {sorted.map((item, index) => {
          const tagKey = (item.tag?.toLowerCase() ?? "") as ReadingTag;
          const tagLabel = READING_TAG_LABELS[tagKey] ?? item.tag;
          const status = evaluateGlucose(item.value_mg_dl, item.tag);

          return (
            <View
              key={`${item.taken_at}-${index}`}
              style={styles.card}
              accessibilityLabel={`Reading of ${item.value_mg_dl ?? "unrecorded"} mg/dL taken on ${formatTimestamp(item.taken_at)}`}
              accessible
            >
              {/* Colored Status Accent Strip */}
              <View
                style={[
                  styles.statusAccentStrip,
                  { backgroundColor: status.color },
                ]}
              />

              <View style={styles.cardContent}>
                {/* Upper Row: Value + Context Badges */}
                <View style={styles.cardHeader}>
                  <View style={styles.valueRow}>
                    <Text style={styles.valueText} allowFontScaling>
                      {item.value_mg_dl !== null && item.value_mg_dl !== undefined
                        ? `${item.value_mg_dl}`
                        : "—"}
                    </Text>
                    <Text style={styles.unitText} allowFontScaling>
                      mg/dL
                    </Text>
                  </View>

                  <View style={styles.badgeRow}>
                    {tagLabel ? <Badge label={tagLabel} tone="info" /> : null}
                    {item.confirmed ? (
                      <Badge label="Confirmed" tone="neutral" />
                    ) : null}
                  </View>
                </View>

                {/* Meta Row: Glycemic Tier + Timestamp */}
                <View style={styles.cardMetaRow}>
                  <View
                    style={[
                      styles.statusPill,
                      {
                        backgroundColor: status.bgColor,
                        borderColor: status.borderColor,
                      },
                    ]}
                  >
                    <Ionicons
                      name={
                        status.category === "target"
                          ? "checkmark-circle"
                          : status.category === "elevated"
                          ? "trending-up"
                          : status.category === "low"
                          ? "alert-circle"
                          : "warning"
                      }
                      size={11}
                      color={status.color}
                      style={{ marginRight: 3 }}
                    />
                    <Text
                      style={[styles.statusPillText, { color: status.color }]}
                      allowFontScaling
                    >
                      {status.label}
                    </Text>
                  </View>

                  <View style={styles.timestampRow}>
                    <Ionicons
                      name="time-outline"
                      size={12}
                      color={palette.muted}
                      style={{ marginRight: 4 }}
                    />
                    <Text style={styles.timestampText} allowFontScaling>
                      {formatTimestamp(item.taken_at)}
                    </Text>
                  </View>
                </View>

                {/* Lower Row: Clinical Description */}
                <Text style={styles.statusDescription} numberOfLines={1} allowFontScaling>
                  {status.description}
                </Text>
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
    gap: spacing.sm,
  },
  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  headerLeft: {
    flex: 1,
    marginRight: spacing.sm,
  },
  title: {
    fontSize: 16,
    fontWeight: "800",
    color: palette.ink,
    letterSpacing: -0.3,
  },
  subtitle: {
    fontSize: 11,
    color: palette.muted,
    marginTop: 1,
  },
  countBadge: {
    backgroundColor: colors.surface,
    paddingHorizontal: 9,
    paddingVertical: 4,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: palette.border,
  },
  countBadgeText: {
    fontSize: 11,
    fontWeight: "700",
    color: palette.bold,
  },
  list: {
    gap: spacing.sm,
  },
  card: {
    flexDirection: "row",
    backgroundColor: colors.surface,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: palette.border,
    overflow: "hidden",
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.05,
    shadowRadius: 10,
    elevation: 2,
  },
  statusAccentStrip: {
    width: 4,
  },
  cardContent: {
    flex: 1,
    padding: spacing.md - 2,
    gap: spacing.sm,
  },
  cardHeader: {
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
  },
  valueRow: {
    flexDirection: "row",
    alignItems: "baseline",
    gap: 4,
  },
  valueText: {
    fontSize: 22,
    fontWeight: "800",
    color: palette.ink,
    letterSpacing: -0.4,
  },
  unitText: {
    fontSize: 11,
    fontWeight: "700",
    color: palette.muted,
  },
  badgeRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    flexWrap: "wrap",
    justifyContent: "flex-end",
    marginTop: 2,
  },
  cardMetaRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  statusPill: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radii.pill,
    borderWidth: 1,
  },
  statusPillText: {
    fontSize: 10,
    fontWeight: "800",
  },
  timestampRow: {
    flexDirection: "row",
    alignItems: "center",
    flexShrink: 1,
  },
  timestampText: {
    fontSize: 11,
    fontWeight: "600",
    color: palette.muted,
  },
  statusDescription: {
    fontSize: 12,
    color: palette.muted,
    borderTopWidth: 1,
    borderTopColor: palette.hairline,
    paddingTop: spacing.xs,
    lineHeight: 16,
  },
});