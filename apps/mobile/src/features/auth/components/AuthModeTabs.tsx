import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { colors, radii, typography } from "../../../theming/tokens";

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
    minHeight: 56,
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#EDF3F6",
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: "#DCE6EA",
    padding: 4,
    gap: 4,
  },
  tab: {
    flex: 1,
    minHeight: 46,
    borderRadius: radii.pill,
    alignItems: "center",
    justifyContent: "center",
  },
  tabActive: {
    backgroundColor: colors.surface,
    shadowColor: "#0D5C75",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.12,
    shadowRadius: 8,
    elevation: 3,
  },
  tabPressed: {
    opacity: 0.78,
  },
  tabText: {
    fontSize: typography.fontSize.bodySmall,
    color: "#5B727D",
    fontWeight: "600",
    letterSpacing: 0.1,
  },
  tabTextActive: {
    color: "#0A485C",
    fontWeight: "700",
  },
});
