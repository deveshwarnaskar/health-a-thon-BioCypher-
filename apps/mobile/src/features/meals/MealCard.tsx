import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Badge } from "../../components/primitives/Badge";
import { colors, spacing } from "../../theming/tokens";
import type { PatientMealObservation } from "../../services/schemas/clinical";

export type MealCardProps = {
  item: PatientMealObservation;
  testID?: string;
};

/**
 * Consistent clinical palettes for the logbook (anchored to design tokens).
 */
const palette = {
  muted: "#64748B",
  faint: "#94A3B8",
  ink: "#0F172A",
  confirmed: "#059669",
  confirmedBg: "#ECFDF5",
  confirmedBorder: "#A7F3D0",
  pending: "#D97706",
  pendingBg: "#FFFBEB",
  pendingBorder: "#FDE68A",
  border: "rgba(15, 23, 42, 0.07)",
  hairline: "#EEF2F7",
} as const;

export function MealCard({ item, testID }: MealCardProps) {
  const formattedDate = React.useMemo(() => {
    try {
      const date = new Date(item.recorded_at);
      return date.toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return item.recorded_at;
    }
  }, [item.recorded_at]);

  const confirmed = item.confirmed === true;
  const statusAccent = confirmed ? palette.confirmed : palette.pending;

  const card = (
    <View
      style={styles.card}
      accessible
      accessibilityLabel={`Meal ${item.description}, ${confirmed ? "confirmed" : "pending confirmation"}`}
    >
      {/* Colored Status Accent Strip */}
      <View style={[styles.statusAccentStrip, { backgroundColor: statusAccent }]} />

      <View style={styles.cardContent}>
        {/* Upper Row: Description + Status Badge */}
        <View style={styles.cardHeader}>
          <Text style={styles.description} numberOfLines={2} allowFontScaling>
            {item.description}
          </Text>
          <Badge
            label={confirmed ? "Confirmed" : "Draft"}
            tone={confirmed ? "success" : "warning"}
          />
        </View>

        {/* Meta Row: Portion + Timestamp */}
        <View style={styles.cardMetaRow}>
          <View style={styles.timestampRow}>
            <Ionicons name="time-outline" size={12} color={palette.muted} style={{ marginRight: 4 }} />
            <Text style={styles.timestampText} allowFontScaling>
              {formattedDate}
            </Text>
          </View>

          {item.portion_label ? (
            <Text style={styles.portion} numberOfLines={1} allowFontScaling>
              {item.portion_label}
              {item.quantity != null ? ` (${item.quantity}x)` : ""}
            </Text>
          ) : null}
        </View>
      </View>
    </View>
  );

  return testID ? <View testID={testID}>{card}</View> : card;
}

const styles = StyleSheet.create({
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
    gap: spacing.sm,
  },
  description: {
    flex: 1,
    fontSize: 15,
    fontWeight: "700",
    color: palette.ink,
    lineHeight: 21,
    letterSpacing: -0.2,
  },
  cardMetaRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: palette.hairline,
    paddingTop: spacing.xs,
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
  portion: {
    fontSize: 11,
    fontWeight: "700",
    color: palette.ink,
    flexShrink: 1,
    textAlign: "right",
  },
});