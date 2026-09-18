import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { colors, typography, radii, spacing } from "../../theming/tokens";
import type { SyncStatus } from "../../db/repositories";
import { useTranslation } from "../../i18n/i18n";

export interface SyncStatusBadgeProps {
  status: SyncStatus;
  compact?: boolean;
}

export function SyncStatusBadge({ status, compact = false }: SyncStatusBadgeProps) {
  const { t } = useTranslation();

  const config = getStatusConfig(status, t);

  return (
    <View
      style={[styles.container, { backgroundColor: config.backgroundColor }]}
      accessible={true}
      accessibilityRole="text"
      accessibilityLabel={`${t("accessibility.syncStatusLabel")}: ${config.label}`}
    >
      <Text style={[styles.icon, { color: config.textColor }]} allowFontScaling={true}>
        {config.glyph}
      </Text>
      {!compact && (
        <Text
          style={[styles.label, { color: config.textColor }]}
          allowFontScaling={true}
          numberOfLines={1}
        >
          {config.label}
        </Text>
      )}
    </View>
  );
}

function getStatusConfig(
  status: SyncStatus,
  t: (key: string) => string
): {
  label: string;
  glyph: string;
  backgroundColor: string;
  textColor: string;
} {
  switch (status) {
    case "SAVED_LOCALLY":
      return {
        label: t("sync.savedLocally"),
        glyph: "💾",
        backgroundColor: "#E8F4F8",
        textColor: colors.primary,
      };
    case "WAITING_TO_SYNC":
      return {
        label: t("sync.waitingToSync"),
        glyph: "⏳",
        backgroundColor: "#FFF8E7",
        textColor: colors.warning,
      };
    case "SYNCING":
      return {
        label: t("sync.syncing"),
        glyph: "🔄",
        backgroundColor: "#EBF5FB",
        textColor: colors.info,
      };
    case "SYNCED":
      return {
        label: t("sync.synced"),
        glyph: "✓",
        backgroundColor: "#E8F8F0",
        textColor: colors.leafGreen,
      };
    case "NEEDS_ATTENTION":
      return {
        label: t("sync.needsAttention"),
        glyph: "⚠",
        backgroundColor: "#FDEDEC",
        textColor: colors.critical,
      };
  }
}

const styles = StyleSheet.create({
  container: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xxs,
    borderRadius: radii.pill,
    minHeight: 28,
    gap: spacing.xs,
    alignSelf: "flex-start",
  },
  icon: {
    fontSize: typography.fontSize.bodySmall,
    lineHeight: typography.lineHeight.bodySmall,
    fontWeight: typography.weight.bold,
  },
  label: {
    fontSize: typography.fontSize.caption,
    lineHeight: typography.lineHeight.caption,
    fontWeight: typography.weight.semibold,
  },
});
