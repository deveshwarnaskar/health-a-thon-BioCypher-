import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Badge } from "../../components/primitives/Badge";
import { Button } from "../../components/primitives/Button";
import { colors, spacing } from "../../theming/tokens";
import type { LogMealResponse } from "../../services/schemas/meals";

export type MealDraftSummaryProps = {
  draft: LogMealResponse;
  description: string;
  onConfirm: () => void;
  onDiscard?: () => void;
  isConfirming?: boolean;
  testID?: string;
};

/**
 * Consistent clinical palettes for the logbook (anchored to design tokens).
 */
const palette = {
  teal700: "#0F766E",
  teal600: "#0D9488",
  tealBg: "#F0FDFA",
  tealBorder: "#A7F3D2",
  ink: "#0F172A",
  body: "#334155",
  muted: "#64748B",
  border: "rgba(15, 23, 42, 0.07)",
  hairline: "#EEF2F7",
} as const;

export function MealDraftSummary({
  draft,
  description,
  onConfirm,
  onDiscard,
  isConfirming = false,
  testID,
}: MealDraftSummaryProps) {
  const card = (
    <View
      style={styles.card}
      accessible
      accessibilityLabel={`Meal draft ${description} pending confirmation`}
    >
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerIconCircle}>
          <Ionicons name="restaurant" size={17} color={palette.teal600} />
        </View>
        <Text style={styles.title} allowFontScaling>
          Meal Draft Summary
        </Text>
        <Badge label="Pending Confirmation" tone="warning" />
      </View>

      <Text style={styles.description} allowFontScaling>
        {description}
      </Text>

      {draft.portion_label ? (
        <View style={styles.portionRow}>
          <Ionicons name="scale-outline" size={13} color={palette.muted} style={{ marginRight: 5 }} />
          <Text style={styles.portionLabel} allowFontScaling>
            Portion: {draft.portion_label} katori
            {draft.quantity != null ? ` (${draft.quantity}x)` : ""}
          </Text>
        </View>
      ) : null}

      <Text style={styles.hint} allowFontScaling>
        Review your meal details and tap below to confirm. Server confirmation is required to finalize this entry.
      </Text>

      <View style={styles.actions}>
        <Button
          label={isConfirming ? "Confirming…" : "Confirm Meal"}
          variant="primary"
          onPress={onConfirm}
          disabled={isConfirming}
          accessibilityHint="Submits confirmation to finalize this meal record on the server"
        />
        {onDiscard ? (
          <Button
            label="Discard Draft"
            variant="ghost"
            onPress={onDiscard}
            disabled={isConfirming}
            accessibilityHint="Discards this draft without confirming"
          />
        ) : null}
      </View>
    </View>
  );

  return testID ? <View testID={testID}>{card}</View> : card;
}

const styles = StyleSheet.create({
  card: {
    padding: spacing.md + 2,
    backgroundColor: colors.surface,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: palette.border,
    gap: spacing.sm,
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.06,
    shadowRadius: 22,
    elevation: 3,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  headerIconCircle: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: palette.tealBg,
    alignItems: "center",
    justifyContent: "center",
  },
  title: {
    flex: 1,
    fontSize: 16,
    fontWeight: "800",
    color: palette.ink,
    letterSpacing: -0.3,
  },
  description: {
    fontSize: 15,
    fontWeight: "600",
    color: palette.ink,
    lineHeight: 21,
  },
  portionRow: {
    flexDirection: "row",
    alignItems: "center",
  },
  portionLabel: {
    fontSize: 12,
    fontWeight: "600",
    color: palette.body,
  },
  hint: {
    fontSize: 12,
    lineHeight: 17,
    color: palette.muted,
    borderTopWidth: 1,
    borderTopColor: palette.hairline,
    paddingTop: spacing.sm,
  },
  actions: {
    gap: spacing.sm,
  },
});