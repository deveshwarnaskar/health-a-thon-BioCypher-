import React from "react";
import { ActivityIndicator, StyleSheet, Text, View } from "react-native";
import { colors, spacing, typography } from "../../theming/tokens";

export type LoadingStateProps = {
  label?: string;
  testID?: string;
};

export function LoadingState({ label = "Loading", testID }: LoadingStateProps) {
  return (
    <View
      style={styles.container}
      testID={testID}
      accessible
      accessibilityRole="progressbar"
      accessibilityLabel={label}
      accessibilityLiveRegion="polite"
    >
      <ActivityIndicator size="large" color={colors.primary} />
      <Text style={styles.label} allowFontScaling>
        {label}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.md,
    padding: spacing.xl,
    backgroundColor: colors.background,
  },
  label: {
    fontSize: typography.fontSize.body,
    color: colors.textSecondary,
    fontWeight: "700",
  },
});
