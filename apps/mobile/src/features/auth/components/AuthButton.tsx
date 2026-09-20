import React from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  type StyleProp,
  View,
  type ViewStyle,
} from "react-native";
import { colors, radii, spacing, typography } from "../../../theming/tokens";

export type AuthButtonProps = {
  label: string;
  loadingLabel?: string;
  onPress: () => void;
  variant?: "primary" | "secondary" | "outline" | "ghost";
  disabled?: boolean;
  busy?: boolean;
  accessibilityHint?: string;
  accessibilityLabel?: string;
  testID?: string;
  style?: StyleProp<ViewStyle>;
};

export function AuthButton({
  label,
  loadingLabel,
  onPress,
  variant = "primary",
  disabled = false,
  busy = false,
  accessibilityHint,
  accessibilityLabel,
  testID,
  style,
}: AuthButtonProps) {
  const isDisabled = disabled || busy;
  const isPrimary = variant === "primary";
  const isSecondary = variant === "secondary";
  const isOutline = variant === "outline";
  const isGhost = variant === "ghost";

  const displayLabel = busy && loadingLabel ? loadingLabel : label;

  return (
    <Pressable
      onPress={onPress}
      disabled={isDisabled}
      testID={testID}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel ?? displayLabel}
      accessibilityHint={accessibilityHint}
      accessibilityState={{ disabled: isDisabled, busy }}
      style={({ pressed }) => [
        styles.base,
        isPrimary && styles.primary,
        isSecondary && styles.secondary,
        isOutline && styles.outline,
        isGhost && styles.ghost,
        isDisabled && styles.disabled,
        pressed && !isDisabled && styles.pressed,
        style,
      ]}
    >
      {busy ? (
        <View style={styles.busyRow}>
          <ActivityIndicator
            size="small"
            color={isPrimary ? "#FFFFFF" : colors.primary}
          />
          <Text
            style={[
              styles.labelText,
              isPrimary && styles.labelPrimary,
              (isOutline || isGhost) && styles.labelOutline,
              isSecondary && styles.labelSecondary,
            ]}
            allowFontScaling
          >
            {displayLabel}
          </Text>
        </View>
      ) : (
        <Text
          style={[
            styles.labelText,
            isPrimary && styles.labelPrimary,
            (isOutline || isGhost) && styles.labelOutline,
            isSecondary && styles.labelSecondary,
          ]}
          allowFontScaling
        >
          {displayLabel}
        </Text>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    minHeight: 58,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing.lg,
    borderRadius: radii.pill,
    borderWidth: 1.5,
    overflow: "hidden",
  },
  primary: {
    backgroundColor: colors.assistive,
    borderColor: colors.assistive,
    shadowColor: "#7A3500",
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.16,
    shadowRadius: 14,
    elevation: 3,
  },
  secondary: {
    backgroundColor: "#F0F7F9",
    borderColor: "#BCE0EB",
  },
  outline: {
    backgroundColor: colors.surface,
    borderColor: colors.primary,
  },
  ghost: {
    backgroundColor: "transparent",
    borderColor: "transparent",
  },
  disabled: {
    opacity: 0.5,
  },
  pressed: {
    opacity: 0.85,
  },
  busyRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
  },
  labelText: {
    fontSize: typography.fontSize.body,
    fontWeight: "700",
    letterSpacing: 0,
  },
  labelPrimary: {
    color: "#FFFFFF",
  },
  labelSecondary: {
    color: colors.primary,
  },
  labelOutline: {
    color: colors.primary,
  },
});
