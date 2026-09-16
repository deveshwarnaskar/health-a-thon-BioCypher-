import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { colors, spacing, typography } from "../../theming/tokens";
import { IconButton } from "./Button";

export type TopAppBarProps = {
  title: string;
  onBack?: () => void;
  leadingLabel?: string;
  actions?: React.ReactNode;
};

export function TopAppBar({ title, onBack, leadingLabel, actions }: TopAppBarProps) {
  const insets = useSafeAreaInsets();

  return (
    <View style={[styles.bar, { paddingTop: insets.top + spacing.sm }]} accessibilityRole="header">
      {onBack ? (
        <IconButton label={leadingLabel ?? "Back"} onPress={onBack}>
          <Text style={styles.backGlyph} allowFontScaling>
            {"<"}
          </Text>
        </IconButton>
      ) : null}
      <Text style={styles.title} numberOfLines={1} allowFontScaling>
        {title}
      </Text>
      {actions ? <View style={styles.actions}>{actions}</View> : <View style={styles.actions} />}
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: spacing.md,
    paddingBottom: spacing.sm,
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    gap: spacing.sm,
  },
  title: {
    flex: 1,
    fontSize: typography.fontSize.title,
    fontWeight: "600",
    color: colors.textPrimary,
  },
  backGlyph: {
    fontSize: typography.fontSize.headline,
    color: colors.primary,
  },
  actions: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
  },
});