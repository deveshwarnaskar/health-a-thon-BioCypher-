import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { colors, spacing, typography } from "../../theming/tokens";

export type EmptyStateProps = {
  title: string;
  message?: string;
  children?: React.ReactNode;
};

export function EmptyState({ title, message, children }: EmptyStateProps) {
  return (
    <View style={styles.container} accessible accessibilityRole="summary" accessibilityLabel={title}>
      <Text style={styles.title} allowFontScaling>
        {title}
      </Text>
      {message ? (
        <Text style={styles.message} allowFontScaling>
          {message}
        </Text>
      ) : null}
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm,
    padding: spacing.xl,
  },
  title: {
    fontSize: typography.fontSize.title,
    fontWeight: "600",
    color: colors.textPrimary,
    textAlign: "center",
  },
  message: {
    fontSize: typography.fontSize.body,
    color: colors.textSecondary,
    textAlign: "center",
  },
});