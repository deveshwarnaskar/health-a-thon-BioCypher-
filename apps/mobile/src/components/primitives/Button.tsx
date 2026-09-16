import React from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import { colors, radii, spacing, touchTarget } from "../../theming/tokens";
import {
  resolveButtonAccessibilityProps,
  touchTargetStyle,
} from "./button.accessibility";

export type ButtonVariant = "primary" | "assistive" | "outline" | "danger" | "ghost";

export type ButtonProps = {
  label: string;
  onPress: () => void;
  variant?: ButtonVariant;
  disabled?: boolean;
  busy?: boolean;
  accessibilityHint?: string;
  accessibilityLabel?: string;
  style?: View["props"]["style"];
};

const variantBackground: Record<ButtonVariant, string> = {
  primary: colors.primary,
  assistive: colors.assistive,
  outline: colors.surface,
  danger: colors.critical,
  ghost: "transparent",
};

const variantForeground: Record<ButtonVariant, string> = {
  primary: colors.textOnPrimary,
  assistive: colors.textOnAssistive,
  outline: colors.primary,
  danger: colors.textOnPrimary,
  ghost: colors.primary,
};

const variantBorder: Record<ButtonVariant, string> = {
  primary: colors.primary,
  assistive: colors.assistive,
  outline: colors.primary,
  danger: colors.critical,
  ghost: "transparent",
};

export function Button({
  label,
  onPress,
  variant = "primary",
  disabled = false,
  busy = false,
  accessibilityHint,
  accessibilityLabel,
  style,
}: ButtonProps) {
  const isDisabled = disabled || busy;
  const a11y = resolveButtonAccessibilityProps({
    label: accessibilityLabel ?? label,
    hint: accessibilityHint,
    disabled,
    busy,
  });

  return (
    <Pressable
      onPress={onPress}
      disabled={isDisabled}
      {...a11y}
      style={({ pressed }) => [
        styles.base,
        touchTargetStyle(),
        {
          backgroundColor: variantBackground[variant],
          borderColor: variantBorder[variant],
          opacity: isDisabled ? 0.5 : pressed ? 0.85 : 1,
        },
        style,
      ]}
    >
      {busy ? (
        <ActivityIndicator color={variantForeground[variant]} />
      ) : (
        <Text style={[styles.label, { color: variantForeground[variant] }]}>{label}</Text>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing.lg,
    borderRadius: radii.md,
    borderWidth: 1,
  },
  label: {
    fontSize: 16,
    fontWeight: "600",
  },
  iconButton: {
    alignItems: "center",
    justifyContent: "center",
  },
});

export type IconButtonProps = {
  label: string;
  onPress: () => void;
  children: React.ReactNode;
  disabled?: boolean;
  accessibilityHint?: string;
  style?: View["props"]["style"];
};

export function IconButton({
  label,
  onPress,
  children,
  disabled = false,
  accessibilityHint,
  style,
}: IconButtonProps) {
  const a11y = resolveButtonAccessibilityProps({ label, hint: accessibilityHint, disabled });

  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      {...a11y}
      hitSlop={touchTarget.hitSlop}
      style={({ pressed }) => [
        styles.iconButton,
        touchTargetStyle(),
        { opacity: disabled ? 0.4 : pressed ? 0.6 : 1 },
        style,
      ]}
    >
      {children}
    </Pressable>
  );
}