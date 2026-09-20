import React, { useContext } from "react";
import { StyleSheet, Text, View } from "react-native";
import { SafeAreaInsetsContext } from "react-native-safe-area-context";
import { colors, radii, spacing, typography } from "../../../theming/tokens";

export type AuthLogoProps = {
  compact?: boolean;
  tone?: "dark" | "light";
};

export function AuthLogo({ compact = false, tone = "dark" }: AuthLogoProps) {
  const isLight = tone === "light";

  return (
    <View style={styles.container} accessibilityRole="header">
      <View style={styles.brandRow}>
        <Text
          style={[
            styles.wordmark,
            isLight && styles.wordmarkLight,
            compact && styles.wordmarkCompact,
          ]}
          allowFontScaling
        >
          THALI × P.L.A.T.E.
        </Text>
        <View style={[styles.tag, isLight && styles.tagLight]}>
          <Text style={[styles.tagText, isLight && styles.tagTextLight]} allowFontScaling>
            HEALTHCARE PLATFORM
          </Text>
        </View>
      </View>
      {!compact && (
        <Text style={[styles.subtext, isLight && styles.subtextLight]} allowFontScaling>
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

export function AuthHeader({ title, subtitle, badge, compactLogo = true }: AuthHeaderProps) {
  const insets = useContext(SafeAreaInsetsContext) ?? {
    bottom: 0,
    left: 0,
    right: 0,
    top: 0,
  };

  return (
    <View
      style={[
        styles.headerContainer,
        { paddingTop: insets.top + spacing.lg },
      ]}
    >
      <View style={styles.decorOrbPrimary} />
      <View style={styles.decorOrbSecondary} />
      <View style={styles.decorRing} />
      <View style={styles.decorGlowBottom} />

      <AuthLogo compact={compactLogo} tone="light" />
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
    alignItems: "center",
    zIndex: 1,
  },
  brandRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    flexWrap: "wrap",
    gap: spacing.xs,
  },
  wordmark: {
    fontSize: 22,
    fontWeight: "800",
    color: colors.primary,
    letterSpacing: 0.8,
  },
  wordmarkLight: {
    color: colors.textOnPrimary,
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
  tagLight: {
    backgroundColor: "rgba(255, 255, 255, 0.16)",
    borderColor: "rgba(255, 255, 255, 0.28)",
  },
  tagText: {
    fontSize: 10,
    fontWeight: "700",
    color: colors.primary,
    letterSpacing: 0.8,
  },
  tagTextLight: {
    color: "#E0F7FA",
  },
  subtext: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    fontWeight: "400",
    letterSpacing: 0.2,
  },
  subtextLight: {
    color: "#D9EEF4",
  },
  headerContainer: {
    minHeight: 224,
    backgroundColor: "#0A4658",
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.xxl,
    justifyContent: "center",
    gap: spacing.xs,
    overflow: "hidden",
  },
  badgeWrapper: {
    alignSelf: "center",
    backgroundColor: "rgba(255, 255, 255, 0.16)",
    paddingVertical: 3,
    paddingHorizontal: spacing.sm,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.28)",
    zIndex: 1,
  },
  badgeText: {
    fontSize: 11,
    fontWeight: "700",
    color: "#E0F7FA",
    letterSpacing: 0.6,
  },
  title: {
    fontSize: typography.fontSize.display,
    fontWeight: "800",
    color: "#FFFFFF",
    lineHeight: typography.lineHeight.display,
    textAlign: "center",
    zIndex: 1,
  },
  subtitle: {
    fontSize: typography.fontSize.body,
    color: "#D0E9F0",
    lineHeight: typography.lineHeight.body,
    textAlign: "center",
    zIndex: 1,
  },
  decorOrbPrimary: {
    position: "absolute",
    width: 260,
    height: 260,
    borderRadius: 130,
    backgroundColor: "rgba(34, 211, 238, 0.09)",
    top: -60,
    right: -40,
  },
  decorOrbSecondary: {
    position: "absolute",
    width: 200,
    height: 200,
    borderRadius: 100,
    backgroundColor: "rgba(45, 212, 191, 0.08)",
    bottom: -40,
    left: -50,
  },
  decorRing: {
    position: "absolute",
    width: 140,
    height: 140,
    borderRadius: 70,
    borderWidth: 1.5,
    borderColor: "rgba(255, 255, 255, 0.08)",
    top: 24,
    left: 20,
  },
  decorGlowBottom: {
    position: "absolute",
    width: "100%",
    height: 48,
    bottom: 0,
    backgroundColor: "rgba(255, 255, 255, 0.04)",
  },
});
