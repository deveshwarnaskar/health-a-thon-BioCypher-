import React from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
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

export function BottomNav({ currentTab, onSelectTab, badgeCount }: BottomNavProps) {
  return (
    <View style={styles.container} accessibilityRole="tablist">
      {TABS.map((tab) => {
        const isSelected = currentTab === tab.key;
        const isRecord = tab.key === "record";
        const count = tab.key === "tasks" ? badgeCount?.tasks : undefined;

        return (
          <TouchableOpacity
            key={tab.key}
            style={[styles.tab, isRecord && styles.recordTab]}
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
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: "row",
    backgroundColor: colors.surface,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingBottom: spacing.sm,
    paddingTop: spacing.xs,
    paddingHorizontal: spacing.xs,
    alignItems: "center",
    justifyContent: "space-around",
    minHeight: 58,
  },
  tab: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    minHeight: touchTarget.min,
    paddingVertical: spacing.xxs,
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
