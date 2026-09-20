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
      <View style={styles.decorPanelPrimary} />
      <View style={styles.decorPanelSecondary} />
      <View style={styles.decorPillTop} />
      <View style={styles.decorPillBottom} />

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
    backgroundColor: "#FFFFFF1F",
    borderColor: "#FFFFFF52",
  },
  tagText: {
    fontSize: 10,
    fontWeight: "700",
    color: colors.primary,
    letterSpacing: 0.8,
  },
  tagTextLight: {
    color: colors.textOnPrimary,
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
    minHeight: 232,
    backgroundColor: colors.primary,
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.xxl,
    justifyContent: "center",
    gap: spacing.sm,
    overflow: "hidden",
  },
  badgeWrapper: {
    alignSelf: "center",
    backgroundColor: "#FFFFFF24",
    paddingVertical: 2,
    paddingHorizontal: spacing.xs,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: "#FFFFFF40",
    zIndex: 1,
  },
  badgeText: {
    fontSize: 11,
    fontWeight: "700",
    color: colors.textOnPrimary,
    letterSpacing: 0.5,
  },
  title: {
    fontSize: typography.fontSize.display,
    fontWeight: "800",
    color: colors.textOnPrimary,
    lineHeight: typography.lineHeight.display,
    textAlign: "center",
    zIndex: 1,
  },
  subtitle: {
    fontSize: typography.fontSize.body,
    color: "#E5F5F8",
    lineHeight: typography.lineHeight.body,
    textAlign: "center",
    zIndex: 1,
  },
  decorPanelPrimary: {
    position: "absolute",
    width: 152,
    height: 120,
    borderRadius: 28,
    backgroundColor: "#FFFFFF14",
    transform: [{ rotate: "-18deg" }],
    left: -18,
    top: 48,
  },
  decorPanelSecondary: {
    position: "absolute",
    width: 164,
    height: 132,
    borderRadius: 32,
    backgroundColor: "#E67E2230",
    transform: [{ rotate: "18deg" }],
    right: -22,
    top: 58,
  },
  decorPillTop: {
    position: "absolute",
    width: 104,
    height: 28,
    borderRadius: radii.pill,
    backgroundColor: "#FFFFFF22",
    right: 28,
    top: 30,
  },
  decorPillBottom: {
    position: "absolute",
    width: 230,
    height: 76,
    borderTopLeftRadius: 48,
    borderTopRightRadius: 48,
    backgroundColor: "#E67E2240",
    alignSelf: "center",
    bottom: 0,
  },
});
