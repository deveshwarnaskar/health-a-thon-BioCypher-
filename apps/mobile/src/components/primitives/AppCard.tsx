import React from "react";
import { Pressable, StyleSheet, View, type ViewStyle } from "react-native";
import { colors, radii, spacing } from "../../theming/tokens";
import { resolveButtonAccessibilityProps, touchTargetStyle } from "./button.accessibility";

export type AppCardProps = {
  children: React.ReactNode;
  onPress?: () => void;
  accessibilityLabel?: string;
  style?: ViewStyle;
};

export function AppCard({ children, onPress, accessibilityLabel, style }: AppCardProps) {
  const interactive = Boolean(onPress);

  if (!interactive) {
    return <View style={[styles.base, style]}>{children}</View>;
  }

  const a11y = resolveButtonAccessibilityProps({
    label: accessibilityLabel ?? "Card",
    disabled: false,
  });

  return (
    <Pressable
      onPress={onPress}
      {...a11y}
      style={({ pressed }) => [styles.base, pressed ? styles.pressed : null, touchTargetStyle(), style]}
    >
      {children}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    backgroundColor: colors.surface,
    borderRadius: radii.lg,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    gap: spacing.sm,
    shadowColor: colors.primaryInk,
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.08,
    shadowRadius: 18,
    elevation: 3,
  },
  pressed: {
    opacity: 0.9,
    transform: [{ scale: 0.995 }],
  },
});
