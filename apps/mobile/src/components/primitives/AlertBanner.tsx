import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { colors, radii, spacing, typography } from "../../theming/tokens";

export type AlertTone = "critical" | "warning" | "info" | "success";

export type AlertBannerProps = {
  tone: AlertTone;
  message: string;
  title?: string;
};

const toneBackground: Record<AlertTone, string> = {
  critical: colors.critical,
  warning: colors.warning,
  info: colors.info,
  success: colors.leafGreen,
};

const toneForeground: Record<AlertTone, string> = {
  critical: colors.textOnPrimary,
  warning: colors.textPrimary,
  info: colors.textOnPrimary,
  success: colors.textOnPrimary,
};

export function AlertBanner({ tone, message, title }: AlertBannerProps) {
  return (
    <View
      style={[styles.base, { backgroundColor: toneBackground[tone] }]}
      accessible
      accessibilityRole="alert"
      accessibilityLabel={title ? `${title}: ${message}` : message}
    >
      {title ? (
        <Text style={[styles.title, { color: toneForeground[tone] }]} allowFontScaling>
          {title}
        </Text>
      ) : null}
      <Text style={[styles.message, { color: toneForeground[tone] }]} allowFontScaling>
        {message}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  base: {
    borderRadius: radii.md,
    padding: spacing.md,
    gap: spacing.xxs,
  },
  title: {
    fontSize: typography.fontSize.body,
    fontWeight: "600",
  },
  message: {
    fontSize: typography.fontSize.bodySmall,
  },
});