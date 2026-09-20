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
  critical: colors.tilePink,
  warning: colors.tileCream,
  info: colors.tileAqua,
  success: colors.tileGreen,
};

const toneForeground: Record<AlertTone, string> = {
  critical: colors.critical,
  warning: colors.primaryInk,
  info: colors.primary,
  success: colors.leafGreen,
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
    borderRadius: radii.lg,
    padding: spacing.md,
    gap: spacing.xxs,
    borderWidth: 1,
    borderColor: "#FFFFFF",
    shadowColor: colors.primaryInk,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.06,
    shadowRadius: 14,
    elevation: 2,
  },
  title: {
    fontSize: typography.fontSize.body,
    fontWeight: "800",
  },
  message: {
    fontSize: typography.fontSize.bodySmall,
  },
});
