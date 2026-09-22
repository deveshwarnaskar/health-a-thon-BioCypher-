import React from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors, radii, spacing, touchTarget, typography } from "../../../theming/tokens";
import { useTranslation } from "../../../i18n/i18n";

export type WhatsAppHomeCardProps = {
  onConnect: () => void;
};

export function WhatsAppHomeCard({ onConnect }: WhatsAppHomeCardProps) {
  const { t } = useTranslation();

  return (
    <View style={styles.container}>
      <View style={styles.headerRow}>
        <View style={styles.kickerRow}>
          <View style={styles.badgePill}>
            <Text style={styles.badgePillText}>WHATSAPP</Text>
          </View>
          <Text style={styles.kickerText} allowFontScaling>
            DIRECT CHAT LOGGING
          </Text>
        </View>
        <Ionicons name="logo-whatsapp" size={24} color="#25D366" />
      </View>

      <Text style={styles.title} allowFontScaling>
        {t("whatsapp.homeReminderTitle")}
      </Text>
      <Text style={styles.subtitle} allowFontScaling>
        {t("whatsapp.homeReminderSubtitle")}
      </Text>

      <TouchableOpacity
        style={styles.actionButton}
        onPress={onConnect}
        accessibilityRole="button"
        accessibilityLabel={t("whatsapp.homeConnectAction")}
        activeOpacity={0.8}
      >
        <Text style={styles.actionButtonText} allowFontScaling>
          {t("whatsapp.homeConnectAction")}
        </Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.tileCream,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: "#FFFFFF",
    padding: spacing.md,
    shadowColor: colors.primaryInk,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.05,
    shadowRadius: 14,
    elevation: 2,
  },
  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.xs,
  },
  kickerRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
  },
  badgePill: {
    backgroundColor: "#DCF8C6",
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: radii.pill,
  },
  badgePillText: {
    color: "#075E54",
    fontSize: 9,
    fontWeight: typography.weight.bold,
    letterSpacing: 0.5,
  },
  kickerText: {
    fontSize: 10,
    fontWeight: typography.weight.bold,
    color: colors.textSecondary,
    letterSpacing: 1,
  },
  icon: {
    fontSize: 20,
  },
  title: {
    fontSize: typography.fontSize.body,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
    marginBottom: 4,
  },
  subtitle: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    lineHeight: 18,
    marginBottom: spacing.sm,
  },
  actionButton: {
    alignSelf: "flex-start",
    backgroundColor: "#128C7E",
    paddingHorizontal: spacing.md,
    paddingVertical: 8,
    borderRadius: radii.pill,
    minHeight: touchTarget.min,
    justifyContent: "center",
  },
  actionButtonText: {
    color: "#FFFFFF",
    fontSize: typography.fontSize.caption,
    fontWeight: typography.weight.bold,
  },
});
