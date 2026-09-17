import React from "react";
import { StyleSheet, View } from "react-native";
import { EmptyState } from "../../components/primitives/EmptyState";
import { ErrorState } from "../../components/primitives/ErrorState";
import { LoadingState } from "../../components/primitives/LoadingState";
import { spacing } from "../../theming/tokens";
import { MealCard } from "./MealCard";
import type { PatientMealObservation } from "../../services/schemas/clinical";

export type MealTimelineProps = {
  meals: PatientMealObservation[];
  isLoading: boolean;
  isError: boolean;
  onRetry?: () => void;
  testID?: string;
};

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
    gap: spacing.sm,
  },
});
