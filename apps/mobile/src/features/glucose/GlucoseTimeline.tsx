import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { AppCard } from "../../components/primitives/AppCard";
import { Badge } from "../../components/primitives/Badge";
import { LoadingState } from "../../components/primitives/LoadingState";
import { EmptyState } from "../../components/primitives/EmptyState";
import { ErrorState } from "../../components/primitives/ErrorState";
import { colors, spacing, typography } from "../../theming/tokens";
import {
  READING_TAG_LABELS,
  type PatientGlucoseObservation,
  type ReadingTag,
} from "./types";

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
      <Text style={styles.title} allowFontScaling>
        Recent Readings
      </Text>
      <View style={styles.list}>
        {sorted.map((item, index) => {
          const tagKey = (item.tag?.toLowerCase() ?? "") as ReadingTag;
          const tagLabel = READING_TAG_LABELS[tagKey] ?? item.tag;

          return (
            <AppCard
              key={`${item.taken_at}-${index}`}
              accessibilityLabel={`Reading of ${item.value_mg_dl ?? "unrecorded"} mg/dL taken on ${formatTimestamp(item.taken_at)}`}
            >
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
                  {tagLabel ? (
                    <Badge label={tagLabel} tone="info" />
                  ) : null}
                  {item.confirmed ? (
                    <Badge label="Confirmed" tone="neutral" />
                  ) : null}
                </View>
              </View>

              <Text style={styles.timestampText} allowFontScaling>
                {formatTimestamp(item.taken_at)}
              </Text>
            </AppCard>
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
  title: {
    fontSize: typography.fontSize.title,
    fontWeight: "600",
    color: colors.textPrimary,
  },
  list: {
    gap: spacing.sm,
  },
  cardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  valueRow: {
    flexDirection: "row",
    alignItems: "baseline",
    gap: spacing.xxs,
  },
  valueText: {
    fontSize: typography.fontSize.headline,
    fontWeight: "700",
    color: colors.textPrimary,
  },
  unitText: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: "500",
    color: colors.textSecondary,
  },
  badgeRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
  },
  timestampText: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textSecondary,
    marginTop: spacing.xxs,
  },
});