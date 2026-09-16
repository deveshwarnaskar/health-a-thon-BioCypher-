import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { colors, spacing, typography } from "../../theming/tokens";

export type DividerProps = {
  /** If provided, section label rendered next to the rule. */
  label?: string;
};

export function Divider({ label }: DividerProps) {
  if (label) {
    return (
      <View style={styles.labeled} accessible accessibilityRole="text" accessibilityLabel={label}>
        <View style={styles.line} />
        <Text style={styles.labelText} allowFontScaling>
          {label}
        </Text>
        <View style={styles.line} />
      </View>
    );
  }
  return <View style={styles.line} />;
}

const styles = StyleSheet.create({
  line: {
    height: 1,
    backgroundColor: colors.border,
    flex: 1,
  },
  labeled: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    marginVertical: spacing.sm,
  },
  labelText: {
    color: colors.textSecondary,
    fontSize: typography.fontSize.bodySmall,
    fontWeight: "500",
  },
});