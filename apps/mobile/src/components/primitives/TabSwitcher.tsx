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
    backgroundColor: colors.surface,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: "#FFFFFF",
    padding: spacing.xs,
    gap: spacing.xxs,
    shadowColor: colors.primaryInk,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.07,
    shadowRadius: 16,
    elevation: 2,
  },
  tab: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    minHeight: 40,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.sm,
  },
  tabSelected: {
    backgroundColor: colors.tileAqua,
  },
  label: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textSecondary,
    fontWeight: "700",
  },
  labelSelected: {
    color: colors.primaryInk,
    fontWeight: "800",
  },
});
