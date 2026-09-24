import React from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { colors, radii, spacing, touchTarget, typography } from "../../../theming/tokens";

export type CaregiverTab = "home" | "record" | "you";

export type CaregiverBottomNavProps = {
  currentTab: CaregiverTab;
  onSelectTab: (tab: CaregiverTab) => void;
  testID?: string;
};

type TabItem = {
  key: CaregiverTab;
  label: string;
  iconActive: keyof typeof Ionicons.glyphMap;
  iconInactive: keyof typeof Ionicons.glyphMap;
  accessibilityLabel: string;
};

const TABS: TabItem[] = [
  {
    key: "home",
    label: "Home",
    iconActive: "home",
    iconInactive: "home-outline",
    accessibilityLabel: "Caregiver home tab",
  },
  {
    key: "record",
    label: "Record",
    iconActive: "pulse",
    iconInactive: "pulse-outline",
    accessibilityLabel: "Patient health record tab",
  },
  {
    key: "you",
    label: "You",
    iconActive: "person",
    iconInactive: "person-outline",
    accessibilityLabel: "Caregiver account and profile tab",
  },
];

function useSafeInsetsFallback() {
  try {
    return useSafeAreaInsets();
  } catch {
    return { top: 0, right: 0, bottom: 0, left: 0 };
  }
}

/**
 * Caregiver bottom navigation component for Gate C1 (Home, Record, You).
 * Phone-first, safe-area compatible, minimum touch targets >= 44, accessibilityRole="button".
 */
export function CaregiverBottomNav({
  currentTab,
  onSelectTab,
  testID = "caregiver-bottom-nav",
}: CaregiverBottomNavProps) {
  const insets = useSafeInsetsFallback();
  const bottomPadding = Math.max(insets.bottom, spacing.xs);

  return (
    <View style={[styles.container, { paddingBottom: bottomPadding }]} testID={testID}>
      <View style={styles.navBar}>
        {TABS.map((tab) => {
          const isSelected = currentTab === tab.key;
          return (
            <TouchableOpacity
              key={tab.key}
              style={[styles.tab, isSelected && styles.activeTab]}
              onPress={() => onSelectTab(tab.key)}
              accessibilityRole="button"
              accessibilityLabel={tab.accessibilityLabel}
              accessibilityState={{ selected: isSelected }}
              activeOpacity={0.7}
            >
              <Ionicons
                name={isSelected ? tab.iconActive : tab.iconInactive}
                size={22}
                color={isSelected ? colors.primary : colors.textSecondary}
              />
              <Text
                style={[styles.label, isSelected && styles.activeLabel]}
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
  container: {
    backgroundColor: colors.surface,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingTop: spacing.xs,
  },
  navBar: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-around",
    paddingHorizontal: spacing.md,
  },
  tab: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    minHeight: touchTarget.min,
    paddingVertical: spacing.xxs,
    borderRadius: radii.md,
    gap: 2,
  },
  activeTab: {
    backgroundColor: "rgba(13, 148, 136, 0.08)",
  },
  label: {
    fontSize: 11,
    lineHeight: 14,
    color: colors.textSecondary,
    fontWeight: "500",
  },
  activeLabel: {
    color: colors.primary,
    fontWeight: "700",
  },
});
