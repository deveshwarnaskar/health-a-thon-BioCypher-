import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { EmptyState } from "../../components/primitives/EmptyState";
import { ErrorState } from "../../components/primitives/ErrorState";
import { LoadingState } from "../../components/primitives/LoadingState";
import { colors, radii } from "../../theming/tokens";
import { MealCard } from "./MealCard";
import type { PatientMealObservation } from "../../services/schemas/clinical";

export type MealTimelineProps = {
  meals: PatientMealObservation[];
  isLoading: boolean;
  isError: boolean;
  onRetry?: () => void;
  testID?: string;
};

const palette = {
  bold: "#475569",
  muted: "#64748B",
  ink: "#0F172A",
  border: "rgba(15, 23, 42, 0.07)",
} as const;

export function MealTimeline({
  meals,
  isLoading,
  isError,
  onRetry,
  testID,
}: MealTimelineProps) {
  if (isLoading) {
    return <LoadingState label="Loading meal history…" />;
  }

  if (isError) {
    return (
      <ErrorState
        title="Could not load meals"
        message="Unable to load your meal history. Please check your connection and try again."
        onRetry={onRetry}
      />
    );
  }

  if (meals.length === 0) {
    return (
      <EmptyState
        title="No meals logged yet"
        message="Use the form above to log your first meal."
      />
    );
  }

  return (
    <View style={styles.container} testID={testID}>
      {/* Section Header */}
      <View style={styles.headerRow}>
        <View style={styles.headerLeft}>
          <Text style={styles.title} allowFontScaling>
            Recent Meals
          </Text>
          <Text style={styles.subtitle} allowFontScaling>
            Chronological nutrition log
          </Text>
        </View>
        <View style={styles.countBadge}>
          <Text style={styles.countBadgeText} allowFontScaling>
            {meals.length} {meals.length === 1 ? "entry" : "entries"}
          </Text>
        </View>
      </View>

      {meals.map((meal, index) => (
        <MealCard
          key={`${meal.recorded_at}-${index}`}
          item={meal}
          testID={testID ? `${testID}-item-${index}` : undefined}
        />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: 12,
  },
  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  headerLeft: {
    flex: 1,
    marginRight: 12,
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
});