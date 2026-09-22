import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
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
  const eyebrow = onBack ? undefined : leadingLabel;

  return (
    <View style={[styles.bar, { paddingTop: insets.top + spacing.sm }]} accessibilityRole="header">
      <View style={styles.row}>
        {onBack ? (
          <IconButton label={leadingLabel ?? "Back"} onPress={onBack} style={styles.backButton}>
            <Ionicons name="chevron-back" size={20} color={colors.textPrimary} />
          </IconButton>
        ) : null}
        <View style={styles.titleColumn}>
          {eyebrow ? (
            <Text style={styles.eyebrow} numberOfLines={1} allowFontScaling>
              {eyebrow}
            </Text>
          ) : null}
          <Text style={styles.title} numberOfLines={1} allowFontScaling>
            {title}
          </Text>
        </View>
        {actions ? <View style={styles.actions}>{actions}</View> : <View style={styles.actions} />}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    paddingHorizontal: spacing.md,
    paddingBottom: spacing.md,
    backgroundColor: colors.background,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  titleColumn: {
    flex: 1,
    justifyContent: "center",
  },
  eyebrow: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: "800",
    color: colors.textSecondary,
  },
  title: {
    fontSize: typography.fontSize.headline,
    lineHeight: typography.lineHeight.headline,
    fontWeight: "800",
    color: colors.textPrimary,
  },
  backButton: {
    borderRadius: 999,
    backgroundColor: colors.surface,
    shadowColor: colors.primaryInk,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.08,
    shadowRadius: 12,
    elevation: 2,
  },
  backGlyph: {
    fontSize: typography.fontSize.title,
    color: colors.textPrimary,
    fontWeight: "800",
  },
  actions: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
  },
});
