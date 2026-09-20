import React from "react";
import { Platform, StyleSheet, Text, TouchableOpacity, View, type ViewStyle } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { colors, radii, spacing, touchTarget, typography } from "../../../theming/tokens";
import type { PatientTab } from "../types";

export type BottomNavProps = {
  currentTab: PatientTab;
  onSelectTab: (tab: PatientTab) => void;
  badgeCount?: {
    tasks?: number;
    notifications?: number;
  };
};

type TabItem = {
  key: PatientTab;
  label: string;
  icon: string;
  accessibilityLabel: string;
};

const TABS: TabItem[] = [
  { key: "home", label: "Home", icon: "🏠", accessibilityLabel: "Home tab" },
  { key: "record", label: "Record", icon: "➕", accessibilityLabel: "Record health data" },
  { key: "timeline", label: "Timeline", icon: "📈", accessibilityLabel: "Care timeline history" },
  { key: "tasks", label: "Tasks", icon: "📋", accessibilityLabel: "Care tasks" },
  { key: "you", label: "You", icon: "👤", accessibilityLabel: "Account and profile" },
];

function useSafeInsetsFallback() {
  try {
    return useSafeAreaInsets();
  } catch {
    return { top: 0, right: 0, bottom: 0, left: 0 };
  }
}

const glassWebStyle = Platform.select({
  web: {
    backdropFilter: "blur(20px)",
    WebkitBackdropFilter: "blur(20px)",
  } as unknown as ViewStyle,
  default: {},
});

const FADE_STEPS = [
  { height: 8, bg: "rgba(255, 255, 255, 0.015)" },
  { height: 8, bg: "rgba(255, 255, 255, 0.04)" },
  { height: 8, bg: "rgba(255, 255, 255, 0.08)" },
  { height: 8, bg: "rgba(255, 255, 255, 0.14)" },
  { height: 8, bg: "rgba(255, 255, 255, 0.22)" },
  { height: 10, bg: "rgba(255, 255, 255, 0.32)" },
  { height: 10, bg: "rgba(255, 255, 255, 0.45)" },
  { height: 10, bg: "rgba(255, 255, 255, 0.60)" },
  { height: 12, bg: "rgba(255, 255, 255, 0.75)" },
  { height: 14, bg: "rgba(255, 255, 255, 0.86)" },
];

export function BottomNav({ currentTab, onSelectTab, badgeCount }: BottomNavProps) {
  const insets = useSafeInsetsFallback();
  const bottomOffset = Math.max(insets.bottom, spacing.sm);
  const bottomAreaHeight = bottomOffset + 72 + 60;

  return (
    <View
      style={[
        styles.wrapper,
        { height: bottomAreaHeight },
      ]}
      pointerEvents="box-none"
    >
      {/* Silky-smooth micro-feathered fade into rich whitish blurry wash on the bottom */}
      <View style={styles.blurBackdropContainer} pointerEvents="none">
        {FADE_STEPS.map((step, idx) => (
          <View
            key={idx}
            style={{
              height: step.height,
              backgroundColor: step.bg,
            }}
          />
        ))}
        <View style={[styles.blurMainBody, glassWebStyle]} />
      </View>

      {/* Floating Tabular Pill Navbar */}
      <View
        style={[
          styles.container,
          glassWebStyle,
          { bottom: bottomOffset },
        ]}
        accessibilityRole="tablist"
      >
        {TABS.map((tab) => {
          const isSelected = currentTab === tab.key;
          const isRecord = tab.key === "record";
          const count = tab.key === "tasks" ? badgeCount?.tasks : undefined;

          return (
            <TouchableOpacity
              key={tab.key}
              style={[styles.tab, isSelected && styles.activeTab, isRecord && styles.recordTab]}
              onPress={() => onSelectTab(tab.key)}
              accessibilityRole="tab"
              accessibilityState={{ selected: isSelected }}
              accessibilityLabel={tab.accessibilityLabel}
              activeOpacity={0.7}
            >
              <View style={styles.iconContainer}>
                <Text
                  style={[
                    styles.icon,
                    isSelected && styles.activeIcon,
                    isRecord && styles.recordIcon,
                  ]}
                  allowFontScaling
                >
                  {tab.icon}
                </Text>
                {count && count > 0 ? (
                  <View style={styles.badge} accessibilityElementsHidden>
                    <Text style={styles.badgeText} allowFontScaling>
                      {count > 9 ? "9+" : count}
                    </Text>
                  </View>
                ) : null}
              </View>
              <Text
                style={[
                  styles.label,
                  isSelected && styles.activeLabel,
                  isRecord && styles.recordLabel,
                ]}
                allowFontScaling
              >
                {tab.label}
              </Text>
            </TouchableOpacity>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: {
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
    zIndex: 10,
    justifyContent: "flex-end",
  },
  blurBackdropContainer: {
    ...StyleSheet.absoluteFill,
    justifyContent: "flex-end",
  },
  blurMainBody: {
    flex: 1,
    backgroundColor: "rgba(255, 255, 255, 0.92)",
  },
  container: {
    position: "absolute",
    left: spacing.md,
    right: spacing.md,
    flexDirection: "row",
    backgroundColor: "rgba(255, 255, 255, 0.94)",
    borderWidth: 1.5,
    borderColor: "rgba(255, 255, 255, 0.95)",
    borderRadius: radii.pill,
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.xs,
    alignItems: "center",
    justifyContent: "space-around",
    minHeight: 72,
    shadowColor: colors.primaryInk,
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.12,
    shadowRadius: 20,
    elevation: 8,
  },
  tab: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    minHeight: touchTarget.min,
    paddingVertical: spacing.xxs,
    borderRadius: radii.pill,
  },
  activeTab: {
    backgroundColor: colors.tileAqua,
  },
  recordTab: {
    transform: [{ translateY: -2 }],
  },
  iconContainer: {
    position: "relative",
    alignItems: "center",
    justifyContent: "center",
  },
  icon: {
    fontSize: 20,
    color: colors.textSecondary,
    marginBottom: 2,
  },
  activeIcon: {
    color: colors.primary,
  },
  recordIcon: {
    fontSize: 22,
    color: colors.primary,
  },
  label: {
    fontSize: typography.fontSize.caption,
    lineHeight: typography.lineHeight.caption,
    color: colors.textSecondary,
    fontWeight: typography.weight.medium,
  },
  activeLabel: {
    color: colors.primary,
    fontWeight: typography.weight.bold,
  },
  recordLabel: {
    color: colors.primary,
    fontWeight: typography.weight.semibold,
  },
  badge: {
    position: "absolute",
    top: -4,
    right: -10,
    backgroundColor: colors.assistive,
    borderRadius: radii.pill,
    minWidth: 16,
    height: 16,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 3,
  },
  badgeText: {
    color: colors.textOnAssistive,
    fontSize: 10,
    fontWeight: typography.weight.bold,
    lineHeight: 12,
  },
});
