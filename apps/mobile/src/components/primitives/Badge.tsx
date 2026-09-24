import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { colors, radii, spacing, typography } from "../../theming/tokens";

export type BadgeTone = "neutral" | "success" | "warning" | "critical" | "info" | "assistive";

export type BadgeProps = {
  label: string;
  tone?: BadgeTone;
};

const toneBackground: Record<BadgeTone, string> = {
  neutral: colors.backgroundRaised,
  success: colors.tileGreen,
  warning: colors.tileCream,
  critical: colors.tilePink,
  info: colors.tileAqua,
  assistive: colors.tileYellow,
};

const toneForeground: Record<BadgeTone, string> = {
  neutral: colors.textSecondary,
  success: colors.leafGreen,
  warning: colors.warning,
  critical: colors.critical,
  info: colors.primary,
  assistive: colors.primaryInk,
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
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xxs,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: "#FFFFFF99",
  },
  label: {
    fontSize: typography.fontSize.caption,
    fontWeight: "800",
  },
});
