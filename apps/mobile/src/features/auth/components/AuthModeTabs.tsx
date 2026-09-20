import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { colors, radii, spacing, typography } from "../../../theming/tokens";

export type AuthMode = "login" | "signup";

export type AuthModeTabsProps = {
  activeMode: AuthMode;
  onSelectMode: (mode: AuthMode) => void;
  disabled?: boolean;
};

const options: readonly { mode: AuthMode; label: string }[] = [
  { mode: "login", label: "Sign in" },
  { mode: "signup", label: "Create account" },
];

export function AuthModeTabs({
  activeMode,
  onSelectMode,
  disabled = false,
}: AuthModeTabsProps) {
  return (
    <View style={styles.container} accessibilityRole="tablist">
      {options.map((option) => {
        const isActive = option.mode === activeMode;

        return (
          <Pressable
            key={option.mode}
            accessibilityRole="tab"
            accessibilityLabel={option.label}
            accessibilityState={{ selected: isActive, disabled }}
            disabled={disabled || isActive}
            onPress={() => onSelectMode(option.mode)}
            style={({ pressed }) => [
              styles.tab,
              isActive && styles.tabActive,
              pressed && !disabled && !isActive && styles.tabPressed,
            ]}
          >
            <Text
              style={[styles.tabText, isActive && styles.tabTextActive]}
              allowFontScaling
            >
              {option.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    minHeight: 64,
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#F4F6F7",
    borderRadius: radii.pill,
    padding: spacing.xs,
    gap: spacing.xs,
  },
  tab: {
    flex: 1,
    minHeight: 48,
    borderRadius: radii.pill,
    alignItems: "center",
    justifyContent: "center",
  },
  tabActive: {
    backgroundColor: colors.surface,
    shadowColor: "#0A2833",
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.08,
    shadowRadius: 12,
    elevation: 2,
  },
  tabPressed: {
    opacity: 0.76,
  },
  tabText: {
    fontSize: typography.fontSize.body,
    color: colors.textSecondary,
    fontWeight: "600",
    letterSpacing: 0,
  },
  tabTextActive: {
    color: colors.textPrimary,
    fontWeight: "700",
  },
});
