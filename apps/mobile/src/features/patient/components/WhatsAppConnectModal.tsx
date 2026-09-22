import React from "react";
import {
  Modal,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { colors, radii, spacing, touchTarget, typography } from "../../../theming/tokens";
import { useTranslation } from "../../../i18n/i18n";

export type WhatsAppConnectModalProps = {
  visible: boolean;
  onConnect: () => void;
  onDismiss: () => void;
};

export function WhatsAppConnectModal({
  visible,
  onConnect,
  onDismiss,
}: WhatsAppConnectModalProps) {
  const { t } = useTranslation();

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      onRequestClose={onDismiss}
    >
      <View style={styles.overlay}>
        <View
          style={styles.dialog}
          accessibilityRole="alert"
          accessibilityLabel={t("whatsapp.modalTitle")}
        >
          {/* Header Icon with Glowing Concentric Rings */}
          <View style={styles.heroSection}>
            <View style={styles.iconRingOuter}>
              <View style={styles.iconRingInner}>
                <Text style={styles.iconText}>💬</Text>
              </View>
            </View>

            <View style={styles.categoryPill}>
              <Text style={styles.categoryPillText}>CONNECTED CARE • WHATSAPP SYNC</Text>
            </View>

            <Text style={styles.title} allowFontScaling>
              {t("whatsapp.modalTitle")}
            </Text>
            <Text style={styles.subtitle} allowFontScaling>
              {t("whatsapp.modalSubtitle")}
            </Text>
          </View>

          {/* Benefits Feature Cards */}
          <View style={styles.benefitsList}>
            <View style={styles.benefitCard}>
              <View style={[styles.benefitIconBox, { backgroundColor: "#E0F2FE" }]}>
                <Text style={styles.benefitIcon}>🩸</Text>
              </View>
              <View style={styles.benefitTextBox}>
                <Text style={styles.benefitHeadline} allowFontScaling>
                  Instant Glucose Logging
                </Text>
                <Text style={styles.benefitSubtext} allowFontScaling>
                  {t("whatsapp.benefit1")}
                </Text>
              </View>
            </View>

            <View style={styles.benefitCard}>
              <View style={[styles.benefitIconBox, { backgroundColor: "#DCFCE7" }]}>
                <Text style={styles.benefitIcon}>📸</Text>
              </View>
              <View style={styles.benefitTextBox}>
                <Text style={styles.benefitHeadline} allowFontScaling>
                  Meal Photo Analysis
                </Text>
                <Text style={styles.benefitSubtext} allowFontScaling>
                  {t("whatsapp.benefit2")}
                </Text>
              </View>
            </View>

            <View style={styles.benefitCard}>
              <View style={[styles.benefitIconBox, { backgroundColor: "#FEF3C7" }]}>
                <Text style={styles.benefitIcon}>🔔</Text>
              </View>
              <View style={styles.benefitTextBox}>
                <Text style={styles.benefitHeadline} allowFontScaling>
                  Medication Reminders
                </Text>
                <Text style={styles.benefitSubtext} allowFontScaling>
                  {t("whatsapp.benefit3")}
                </Text>
              </View>
            </View>
          </View>

          {/* Privacy & Trust Reassurance */}
          <View style={styles.privacyBox}>
            <Text style={styles.privacyText}>
              🔒 End-to-end encrypted • ABDM & HIPAA aligned • Clinical care team access only
            </Text>
          </View>

          {/* Action CTAs */}
          <View style={styles.actions}>
            <TouchableOpacity
              style={styles.connectButton}
              onPress={onConnect}
              accessibilityRole="button"
              accessibilityLabel={t("whatsapp.connectButton")}
              activeOpacity={0.85}
            >
              <Text style={styles.connectButtonText} allowFontScaling>
                {t("whatsapp.connectButton")} →
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.dismissButton}
              onPress={onDismiss}
              accessibilityRole="button"
              accessibilityLabel={t("whatsapp.maybeLaterButton")}
              activeOpacity={0.7}
            >
              <Text style={styles.dismissButtonText} allowFontScaling>
                {t("whatsapp.maybeLaterButton")}
              </Text>
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: "rgba(10, 22, 18, 0.72)",
    justifyContent: "center",
    alignItems: "center",
    padding: spacing.md,
  },
  dialog: {
    width: "100%",
    maxWidth: 390,
    backgroundColor: colors.surface,
    borderRadius: 24,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    shadowColor: colors.primaryInk,
    shadowOffset: { width: 0, height: 16 },
    shadowOpacity: 0.2,
    shadowRadius: 32,
    elevation: 12,
  },
  heroSection: {
    alignItems: "center",
    marginBottom: spacing.md,
  },
  iconRingOuter: {
    width: 76,
    height: 76,
    borderRadius: 38,
    backgroundColor: "#E7F9EE",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.xs,
  },
  iconRingInner: {
    width: 54,
    height: 54,
    borderRadius: 27,
    backgroundColor: "#25D366",
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#25D366",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.35,
    shadowRadius: 10,
    elevation: 6,
  },
  iconText: {
    fontSize: 26,
  },
  categoryPill: {
    backgroundColor: "#E6F4F8",
    paddingHorizontal: 10,
    paddingVertical: 3,
    borderRadius: radii.pill,
    marginBottom: spacing.xs,
  },
  categoryPillText: {
    fontSize: 10,
    fontWeight: typography.weight.bold,
    color: colors.primary,
    letterSpacing: 0.8,
  },
  title: {
    fontSize: typography.fontSize.headline,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
    textAlign: "center",
    marginBottom: 4,
  },
  subtitle: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textSecondary,
    textAlign: "center",
    lineHeight: 20,
    paddingHorizontal: spacing.xs,
  },
  benefitsList: {
    gap: spacing.xs + 2,
    marginBottom: spacing.md,
  },
  benefitCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    backgroundColor: "#F8FAFC",
    borderWidth: 1,
    borderColor: "#EEF2F6",
    borderRadius: radii.md,
    padding: spacing.sm,
  },
  benefitIconBox: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
  },
  benefitIcon: {
    fontSize: 18,
  },
  benefitTextBox: {
    flex: 1,
  },
  benefitHeadline: {
    fontSize: 13,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
    marginBottom: 1,
  },
  benefitSubtext: {
    fontSize: 12,
    color: colors.textSecondary,
    lineHeight: 16,
  },
  privacyBox: {
    backgroundColor: "#F1F5F9",
    borderRadius: radii.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
    marginBottom: spacing.md,
  },
  privacyText: {
    fontSize: 11,
    color: colors.textSecondary,
    textAlign: "center",
    lineHeight: 15,
  },
  actions: {
    gap: spacing.xs,
  },
  connectButton: {
    backgroundColor: "#25D366",
    minHeight: 50,
    borderRadius: radii.md,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing.lg,
    shadowColor: "#25D366",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 4,
  },
  connectButtonText: {
    color: "#FFFFFF",
    fontSize: typography.fontSize.body,
    fontWeight: typography.weight.bold,
  },
  dismissButton: {
    minHeight: touchTarget.min,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing.lg,
  },
  dismissButtonText: {
    color: colors.textSecondary,
    fontSize: typography.fontSize.bodySmall,
    fontWeight: typography.weight.semibold,
  },
});
