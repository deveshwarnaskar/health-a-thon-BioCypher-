import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { colors, radii, spacing, typography } from "../../theming/tokens";
import { resolveButtonAccessibilityProps, touchTargetStyle } from "./button.accessibility";

export type ChipProps = {
  label: string;
  selected?: boolean;
  onPress?: () => void;
  disabled?: boolean;
  accessibilityHint?: string;
};

export function Chip({ label, selected = false, onPress, disabled = false, accessibilityHint }: ChipProps) {
  const interactive = Boolean(onPress);
  const a11y = resolveButtonAccessibilityProps({
    label,
    hint: accessibilityHint,
    disabled: disabled || !interactive,
  });
  const accessibilityState = interactive
    ? { ...a11y.accessibilityState, selected }
    : undefined;

  if (!interactive) {
    return (
      <View
        style={[styles.base, selected ? styles.selected : null]}
        accessible
        accessibilityRole="text"
        accessibilityLabel={label}
      >
        <Text style={[styles.label, selected ? styles.labelSelected : null]} allowFontScaling>
          {label}
        </Text>
      </View>
    );
  }

  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      {...a11y}
      accessibilityState={accessibilityState}
      style={({ pressed }) => [
        styles.base,
        selected ? styles.selected : null,
        pressed ? styles.pressed : null,
        disabled ? styles.disabled : null,
        touchTargetStyle(),
      ]}
    >
      <Text style={[styles.label, selected ? styles.labelSelected : null]} allowFontScaling>
        {label}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    minHeight: 32,
    paddingHorizontal: spacing.md,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  selected: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  pressed: {
    opacity: 0.7,
  },
  disabled: {
    opacity: 0.5,
  },
  label: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textPrimary,
  },
  labelSelected: {
    color: colors.textOnPrimary,
    fontWeight: "600",
  },
});