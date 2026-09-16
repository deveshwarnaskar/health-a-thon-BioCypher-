import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { colors, radii, spacing, typography } from "../../theming/tokens";

export type BadgeTone = "neutral" | "success" | "warning" | "critical" | "info" | "assistive";

export type BadgeProps = {
  label: string;
  tone?: BadgeTone;
};

const toneBackground: Record<BadgeTone, string> = {
  neutral: colors.border,
  success: colors.leafGreen,
  warning: colors.warning,
  critical: colors.critical,
  info: colors.info,
  assistive: colors.assistive,
};

const toneForeground: Record<BadgeTone, string> = {
  neutral: colors.textPrimary,
  success: colors.textOnPrimary,
  warning: colors.textPrimary,
  critical: colors.textOnPrimary,
  info: colors.textOnPrimary,
  assistive: colors.textOnAssistive,
};

export function Badge({ label, tone = "neutral" }: BadgeProps) {
  return (
    <View style={[styles.base, { backgroundColor: toneBackground[tone] }]} accessible accessibilityRole="text" accessibilityLabel={label}>
      <Text style={[styles.label, { color: toneForeground[tone] }]} numberOfLines={1} allowFontScaling>
        {label}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  base: {
    alignSelf: "flex-start",
    paddingHorizontal: spacing.xs,
    paddingVertical: spacing.xxs / 2,
    borderRadius: radii.sm,
  },
  label: {
    fontSize: typography.fontSize.caption,
    fontWeight: "600",
  },
});