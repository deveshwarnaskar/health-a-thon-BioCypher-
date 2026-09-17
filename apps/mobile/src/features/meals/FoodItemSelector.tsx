import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { Chip } from "../../components/primitives/Chip";
import { TextInput } from "../../components/primitives/TextInput";
import { colors, spacing, typography } from "../../theming/tokens";
import { COMMON_FOODS, type FoodItem } from "./types";

export type FoodItemSelectorProps = {
  selectedFoodKey: string | null;
  onSelectFood: (food: FoodItem) => void;
  description: string;
  onChangeDescription: (text: string) => void;
  error?: string | null;
  testID?: string;
};

export function FoodItemSelector({
  selectedFoodKey,
  onSelectFood,
  description,
  onChangeDescription,
  error,
  testID,
}: FoodItemSelectorProps) {
  return (
    <View style={styles.container} testID={testID}>
      <Text style={styles.sectionTitle} allowFontScaling>
        Food Items
      </Text>
      <Text style={styles.caption} allowFontScaling>
        Select standard foods or enter your meal description below:
      </Text>

      <View style={styles.chipGrid}>
        {COMMON_FOODS.map((food) => {
          const isSelected = selectedFoodKey === food.key;
          return (
            <Chip
              key={food.key}
              label={food.label}
              selected={isSelected}
              onPress={() => onSelectFood(food)}
              accessibilityHint={`Selects ${food.label} as your meal`}
            />
          );
        })}
      </View>

      <TextInput
        label="Meal Description *"
        value={description}
        onChangeText={onChangeDescription}
        error={error}
        hint="Describe what you are eating (e.g. 1 katori dal with rice)"
        accessibilityHint="Enter description of your meal"
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: spacing.sm,
  },
  sectionTitle: {
    fontSize: typography.fontSize.headline,
    fontWeight: "600",
    color: colors.textPrimary,
  },
  caption: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textSecondary,
  },
  chipGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs,
    marginVertical: spacing.xs,
  },
});
