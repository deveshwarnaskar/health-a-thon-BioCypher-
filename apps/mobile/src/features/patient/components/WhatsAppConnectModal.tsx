import React from "react";
import {
  Modal,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
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
          {/* Header Icon with Concentric Rings */}
          <View style={styles.heroSection}>
            <View style={styles.iconRingOuter}>
              <View style={styles.iconRingInner}>
                <Ionicons name="logo-whatsapp" size={32} color="#25D366" />
              </View>
            </View>

            <View style={styles.categoryPill}>
              <View style={styles.pulseDot} />
              <Text style={styles.categoryPillText} allowFontScaling>
                CONNECTED CARE · WHATSAPP SYNC
              </Text>
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
              <View style={[styles.benefitIconBox, { backgroundColor: "#F0FDFA" }]}>
                <Ionicons name="water-outline" size={18} color="#0D9488" />
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
              <View style={[styles.benefitIconBox, { backgroundColor: "#EFF6FF" }]}>
                <Ionicons name="camera-outline" size={18} color="#2563EB" />
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
              <View style={[styles.benefitIconBox, { backgroundColor: "#FFFBEB" }]}>
                <Ionicons name="notifications-outline" size={18} color="#D97706" />
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
            <Ionicons name="lock-closed" size={12} color="#0D9488" style={{ marginRight: 6 }} />
            <Text style={styles.privacyText} allowFontScaling>
              End-to-end encrypted · ABDM & HIPAA aligned · Care team access only
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
              <Ionicons name="logo-whatsapp" size={18} color="#FFFFFF" style={{ marginRight: 8 }} />
              <Text style={styles.connectButtonText} allowFontScaling>
                {t("whatsapp.connectButton")}
              </Text>
              <Ionicons name="arrow-forward" size={16} color="#FFFFFF" style={{ marginLeft: 6 }} />
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
    backgroundColor: "rgba(15, 23, 42, 0.7)",
    justifyContent: "center",
    alignItems: "center",
    padding: spacing.md,
  },
  dialog: {
    width: "100%",
    maxWidth: 380,
    backgroundColor: colors.surface,
    borderRadius: 24,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 16 },
    shadowOpacity: 0.18,
    shadowRadius: 28,
    elevation: 10,
  },
  heroSection: {
    alignItems: "center",
    marginBottom: spacing.md,
  },
  iconRingOuter: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: "#DCFCE7",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.sm,
  },
  iconRingInner: {
    width: 54,
    height: 54,
    borderRadius: 27,
    backgroundColor: "#F0FDF4",
    alignItems: "center",
    justifyContent: "center",
  },
  categoryPill: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#F0FDFA",
    borderWidth: 1,
    borderColor: "#CCFBF1",
    paddingHorizontal: 10,
    paddingVertical: 3,
    borderRadius: radii.pill,
    marginBottom: spacing.xs + 2,
  },
  pulseDot: {
    width: 5,
    height: 5,
    borderRadius: 2.5,
    backgroundColor: "#0D9488",
    marginRight: 6,
  },
  categoryPillText: {
    fontSize: 9,
    fontWeight: "700",
    color: "#0D9488",
    letterSpacing: 0.8,
  },
  title: {
    fontSize: 18,
    fontWeight: "800",
    color: "#0F172A",
    textAlign: "center",
    letterSpacing: -0.3,
    marginBottom: 4,
  },
  subtitle: {
    fontSize: 12,
    color: "#64748B",
    textAlign: "center",
    lineHeight: 18,
    paddingHorizontal: spacing.sm,
  },
  benefitsList: {
    gap: spacing.xs + 2,
    marginVertical: spacing.sm,
  },
  benefitCard: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#F8FAFC",
    borderRadius: 16,
    padding: spacing.sm + 2,
    borderWidth: 1,
    borderColor: "#EEF2F6",
  },
  benefitIconBox: {
    width: 38,
    height: 38,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacing.sm + 2,
  },
  benefitTextBox: {
    flex: 1,
  },
  benefitHeadline: {
    fontSize: 13,
    fontWeight: "700",
    color: "#0F172A",
  },
  benefitSubtext: {
    fontSize: 11,
    color: "#64748B",
    marginTop: 1,
  },
  privacyBox: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#F0FDFA",
    borderRadius: 12,
    paddingVertical: 6,
    paddingHorizontal: 8,
    borderWidth: 1,
    borderColor: "#CCFBF1",
    marginVertical: spacing.sm,
  },
  privacyText: {
    fontSize: 10,
    color: "#0D9488",
    fontWeight: "600",
    textAlign: "center",
  },
  actions: {
    gap: spacing.xs,
    marginTop: spacing.xs,
  },
  connectButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#128C7E",
    borderRadius: radii.pill,
    minHeight: 48,
    shadowColor: "#128C7E",
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.25,
    shadowRadius: 6,
    elevation: 2,
  },
  connectButtonText: {
    color: "#FFFFFF",
    fontSize: 14,
    fontWeight: "700",
  },
  dismissButton: {
    minHeight: 40,
    alignItems: "center",
    justifyContent: "center",
  },
  dismissButtonText: {
    fontSize: 13,
    fontWeight: "600",
    color: "#64748B",
  },
});
