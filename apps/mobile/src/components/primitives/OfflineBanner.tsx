import React, { useEffect } from "react";
import { View, Text, StyleSheet, AccessibilityInfo } from "react-native";
import { colors, typography, spacing, touchTarget } from "../../theming/tokens";
import { useConnectivity } from "../../connectivity/useConnectivity";
import { useTranslation } from "../../i18n/i18n";

export function OfflineBanner() {
  const { isOffline } = useConnectivity();
  const { t } = useTranslation();

  useEffect(() => {
    if (isOffline) {
      AccessibilityInfo.announceForAccessibility(t("accessibility.offlineModeActive"));
    }
  }, [isOffline, t]);

  if (!isOffline) {
    return null;
  }

  return (
    <View
      style={styles.banner}
      accessible={true}
      accessibilityRole="alert"
      accessibilityLiveRegion="assertive"
      accessibilityLabel={t("accessibility.offlineModeActive")}
    >
      <Text style={styles.icon} allowFontScaling={true}>
        📡
      </Text>
      <Text style={styles.text} allowFontScaling={true}>
        {t("sync.offlineBanner")}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  banner: {
    backgroundColor: colors.warning,
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    gap: spacing.xs,
    minHeight: touchTarget.min,
    width: "100%",
  },
  icon: {
    fontSize: typography.fontSize.body,
    lineHeight: typography.lineHeight.body,
  },
  text: {
    color: colors.textOnPrimary,
    fontSize: typography.fontSize.bodySmall,
    lineHeight: typography.lineHeight.bodySmall,
    fontWeight: typography.weight.medium,
    flex: 1,
    flexWrap: "wrap",
  },
});
