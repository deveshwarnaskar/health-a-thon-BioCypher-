import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { colors, radii, spacing, typography } from "../../../theming/tokens";

export type AuthLogoProps = {
  compact?: boolean;
};

export function AuthLogo({ compact = false }: AuthLogoProps) {
  return (
    <View style={styles.container} accessibilityRole="header">
      <View style={styles.brandRow}>
        <Text style={[styles.wordmark, compact && styles.wordmarkCompact]} allowFontScaling>
          THALI × P.L.A.T.E.
        </Text>
        <View style={styles.tag}>
          <Text style={styles.tagText} allowFontScaling>
            HEALTHCARE PLATFORM
          </Text>
        </View>
      </View>
      {!compact && (
        <Text style={styles.subtext} allowFontScaling>
          Telemetry &amp; Household Assistive Logbook × Precision Lifestyle Assessment &amp; Treatment Engine
        </Text>
      )}
    </View>
  );
}

export type AuthHeaderProps = {
  title: string;
  subtitle?: string;
  badge?: string;
  compactLogo?: boolean;
};

export function AuthHeader({ title, subtitle, badge, compactLogo = false }: AuthHeaderProps) {
  return (
    <View style={styles.headerContainer}>
      <AuthLogo compact={compactLogo} />
      {badge ? (
        <View style={styles.badgeWrapper}>
          <Text style={styles.badgeText} allowFontScaling>
            {badge}
          </Text>
        </View>
      ) : null}
      <Text style={styles.title} allowFontScaling>
        {title}
      </Text>
      {subtitle ? (
        <Text style={styles.subtitle} allowFontScaling>
          {subtitle}
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: spacing.xxs,
    marginBottom: spacing.xs,
  },
  brandRow: {
    flexDirection: "row",
    alignItems: "center",
    flexWrap: "wrap",
    gap: spacing.xs,
  },
  wordmark: {
    fontSize: 22,
    fontWeight: "800",
    color: colors.primary,
    letterSpacing: 0.8,
  },
  wordmarkCompact: {
    fontSize: 18,
    letterSpacing: 0.5,
  },
  tag: {
    backgroundColor: "#E0F2F7",
    paddingHorizontal: spacing.xs,
    paddingVertical: 2,
    borderRadius: radii.sm,
    borderWidth: 1,
    borderColor: "#BCE0EB",
  },
  tagText: {
    fontSize: 10,
    fontWeight: "700",
    color: colors.primary,
    letterSpacing: 0.8,
  },
  subtext: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    fontWeight: "400",
    letterSpacing: 0.2,
  },
  headerContainer: {
    gap: spacing.xs,
    marginBottom: spacing.sm,
  },
  badgeWrapper: {
    alignSelf: "flex-start",
    backgroundColor: "#F0F7F9",
    paddingVertical: 2,
    paddingHorizontal: spacing.xs,
    borderRadius: radii.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  badgeText: {
    fontSize: 11,
    fontWeight: "700",
    color: colors.primary,
    letterSpacing: 0.5,
  },
  title: {
    fontSize: typography.fontSize.headline,
    fontWeight: "700",
    color: colors.textPrimary,
    lineHeight: 30,
  },
  subtitle: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textSecondary,
    lineHeight: 20,
  },
});
