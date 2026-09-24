import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { AppCard } from "../../components/primitives/AppCard";
import { Badge } from "../../components/primitives/Badge";
import { Button } from "../../components/primitives/Button";
import { colors, spacing, typography } from "../../theming/tokens";
import type { LogMealResponse } from "../../services/schemas/meals";

export type MealDraftSummaryProps = {
  draft: LogMealResponse;
  description: string;
  onConfirm: () => void;
  onDiscard?: () => void;
  isConfirming?: boolean;
  testID?: string;
};

export function MealDraftSummary({
  draft,
  description,
  onConfirm,
  onDiscard,
  isConfirming = false,
  testID,
}: MealDraftSummaryProps) {
  const card = (
    <AppCard
      accessibilityLabel={`Meal draft ${description} pending confirmation`}
    >
      <View style={styles.header}>
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
    </AppCard>
  );

  return testID ? <View testID={testID}>{card}</View> : card;
}

const styles = StyleSheet.create({
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spacing.xs,
  },
  title: {
    fontSize: typography.fontSize.headline,
    fontWeight: "600",
    color: colors.textPrimary,
  },
  description: {
    fontSize: typography.fontSize.body,
    fontWeight: "500",
    color: colors.textPrimary,
    marginVertical: spacing.xs,
  },
  portionRow: {
    marginVertical: spacing.xs,
  },
  portionLabel: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textSecondary,
  },
  hint: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    marginVertical: spacing.xs,
  },
  actions: {
    marginTop: spacing.md,
    gap: spacing.sm,
  },
});
