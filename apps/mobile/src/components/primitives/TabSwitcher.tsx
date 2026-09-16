import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { colors, radii, spacing, typography } from "../../theming/tokens";

export type TabSwitcherItem = {
  key: string;
  label: string;
};

export type TabSwitcherProps = {
  items: TabSwitcherItem[];
  selected: string;
  onSelect: (key: string) => void;
  accessibilityHint?: (item: TabSwitcherItem) => string;
};

export function TabSwitcher({ items, selected, onSelect, accessibilityHint }: TabSwitcherProps) {
  return (
    <View style={styles.container} accessibilityRole="tablist">
      {items.map((item) => {
        const isSelected = item.key === selected;
        return (
          <Pressable
            key={item.key}
            onPress={() => onSelect(item.key)}
            accessibilityRole="tab"
            accessibilityLabel={item.label}
            accessibilityHint={accessibilityHint?.(item)}
            accessibilityState={{ selected: isSelected }}
            style={[styles.tab, isSelected ? styles.tabSelected : null]}
            hitSlop={spacing.xxs}
          >
            <Text style={[styles.label, isSelected ? styles.labelSelected : null]} allowFontScaling>
              {item.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: "row",
    backgroundColor: colors.background,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.xxs,
    gap: spacing.xxs,
  },
  tab: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    minHeight: 40,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.sm,
  },
  tabSelected: {
    backgroundColor: colors.surface,
  },
  label: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textSecondary,
    fontWeight: "500",
  },
  labelSelected: {
    color: colors.primary,
    fontWeight: "600",
  },
});