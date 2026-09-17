import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { AppCard } from "../../components/primitives/AppCard";
import { Badge } from "../../components/primitives/Badge";
import { colors, spacing, typography } from "../../theming/tokens";
import type { PatientMealObservation } from "../../services/schemas/clinical";

export type MealCardProps = {
  item: PatientMealObservation;
  testID?: string;
};

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

  const card = (
    <AppCard
      accessibilityLabel={`Meal ${item.description}, ${item.confirmed ? "confirmed" : "pending confirmation"}`}
    >
      <View style={styles.header}>
        <Text style={styles.description} allowFontScaling numberOfLines={2}>
          {item.description}
        </Text>
        {item.confirmed ? (
          <Badge label="Confirmed" tone="success" />
        ) : (
          <Badge label="Draft" tone="warning" />
        )}
      </View>

      {item.portion_label ? (
        <Text style={styles.portion} allowFontScaling>
          Portion: {item.portion_label}
          {item.quantity != null ? ` (${item.quantity}x)` : ""}
        </Text>
      ) : null}

      <Text style={styles.timestamp} allowFontScaling>
        {formattedDate}
      </Text>
    </AppCard>
  );

  return testID ? <View testID={testID}>{card}</View> : card;
}

const styles = StyleSheet.create({
  header: {
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  description: {
    flex: 1,
    fontSize: typography.fontSize.body,
    fontWeight: "600",
    color: colors.textPrimary,
  },
  portion: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textSecondary,
    marginTop: spacing.xs,
  },
  timestamp: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    marginTop: spacing.xs,
  },
});
