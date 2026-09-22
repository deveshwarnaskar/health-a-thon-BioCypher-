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
            DIRECT CHAT TELEMETRY
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
        <Ionicons name="logo-whatsapp" size={17} color="#FFFFFF" style={{ marginRight: 6 }} />
        <Text style={styles.actionButtonText} allowFontScaling>
          {t("whatsapp.homeConnectAction")}
        </Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: "#F0FDF4",
    borderRadius: 20,
    borderWidth: 1,
    borderColor: "#DCFCE7",
    padding: spacing.md,
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 12,
    elevation: 2,
    gap: 4,
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
    paddingHorizontal: 7,
    paddingVertical: 3,
    borderRadius: radii.pill,
  },
  badgePillText: {
    color: "#075E54",
    fontSize: 9,
    fontWeight: "700",
    letterSpacing: 0.5,
  },
  kickerText: {
    fontSize: 10,
    fontWeight: "700",
    color: "#065F46",
    letterSpacing: 0.8,
  },
  title: {
    fontSize: 16,
    fontWeight: "700",
    color: "#0F172A",
  },
  subtitle: {
    fontSize: 13,
    color: "#64748B",
    lineHeight: 18,
    marginBottom: spacing.xs,
  },
  actionButton: {
    flexDirection: "row",
    alignItems: "center",
    alignSelf: "flex-start",
    backgroundColor: "#128C7E",
    paddingHorizontal: spacing.md,
    paddingVertical: 10,
    borderRadius: radii.pill,
    minHeight: touchTarget.min,
    justifyContent: "center",
  },
  actionButtonText: {
    color: "#FFFFFF",
    fontSize: 13,
    fontWeight: "700",
  },
});
