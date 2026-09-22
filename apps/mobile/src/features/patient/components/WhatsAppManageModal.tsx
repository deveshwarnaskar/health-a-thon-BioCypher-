import React, { useState } from "react";
import {
  ActivityIndicator,
  Modal,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors, radii, spacing, touchTarget, typography } from "../../../theming/tokens";
import { useTranslation } from "../../../i18n/i18n";
import { useDisconnectWhatsApp } from "../useWhatsAppIdentity";
import type { WhatsAppIdentityResponse } from "../../../services/schemas/whatsapp";

export type WhatsAppManageModalProps = {
  visible: boolean;
  onClose: () => void;
  identity: WhatsAppIdentityResponse | undefined;
  onDisconnected?: () => void;
};

export function WhatsAppManageModal({
  visible,
  onClose,
  identity,
  onDisconnected,
}: WhatsAppManageModalProps) {
  const { t } = useTranslation();
  const [showConfirmDisconnect, setShowConfirmDisconnect] = useState(false);
  const disconnectMutation = useDisconnectWhatsApp();

  const handleClose = () => {
    setShowConfirmDisconnect(false);
    onClose();
  };

  const handleConfirmDisconnect = async () => {
    try {
      await disconnectMutation.mutateAsync();
      setShowConfirmDisconnect(false);
      onDisconnected?.();
      onClose();
    } catch {
      // Error is handled by mutation state
    }
  };

  const verifiedDateStr = identity?.verified_at
    ? new Date(identity.verified_at).toLocaleDateString()
    : "Active";

  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={handleClose}
    >
      <View style={styles.overlay}>
        <View style={styles.sheet} accessibilityRole="alert">
          {/* Header */}
          <View style={styles.header}>
            <View style={styles.headerTitleRow}>
              <Ionicons name="logo-whatsapp" size={22} color="#25D366" style={{ marginRight: 8 }} />
              <Text style={styles.title} allowFontScaling>
                {t("whatsapp.manageTitle")}
              </Text>
            </View>
            <TouchableOpacity
              onPress={handleClose}
              accessibilityRole="button"
              accessibilityLabel="Close"
              style={styles.closeButton}
            >
              <Ionicons name="close" size={20} color={colors.textPrimary} />
            </TouchableOpacity>
          </View>

          {/* Details Card */}
          <View style={styles.detailsCard}>
            <View style={styles.detailRow}>
              <Text style={styles.detailLabel} allowFontScaling>
                Status
              </Text>
              <View style={styles.statusBadge}>
                <Ionicons name="checkmark-circle" size={14} color="#059669" style={{ marginRight: 4 }} />
                <Text style={styles.statusBadgeText} allowFontScaling>
                  {t("whatsapp.connectedStatus")}
                </Text>
              </View>
            </View>

            <View style={styles.detailDivider} />

            <View style={styles.detailRow}>
              <Text style={styles.detailLabel} allowFontScaling>
                {t("whatsapp.linkedNumberLabel")}
              </Text>
              <Text style={styles.detailValue} allowFontScaling>
                {identity?.phone_number_masked || identity?.phone_number || "Linked"}
              </Text>
            </View>

            <View style={styles.detailDivider} />

            <View style={styles.detailRow}>
              <Text style={styles.detailLabel} allowFontScaling>
                {t("whatsapp.connectedSinceLabel")}
              </Text>
              <Text style={styles.detailValue} allowFontScaling>
                {verifiedDateStr}
              </Text>
            </View>
          </View>

          {/* Supported Features Checklist */}
          <View style={styles.featuresSection}>
            <Text style={styles.featuresSectionTitle} allowFontScaling>
              {t("whatsapp.supportedFeaturesTitle")}
            </Text>
            <View style={styles.featuresList}>
              <View style={styles.featureRow}>
                <View style={styles.featureIconBox}>
                  <Ionicons name="checkmark" size={14} color={colors.primary} />
                </View>
                <Text style={styles.featureLabel} allowFontScaling>
                  {t("whatsapp.featureHealthLogging")}
                </Text>
              </View>

              <View style={styles.featureRow}>
                <View style={styles.featureIconBox}>
                  <Ionicons name="checkmark" size={14} color={colors.primary} />
                </View>
                <Text style={styles.featureLabel} allowFontScaling>
                  {t("whatsapp.featureFoodLogging")}
                </Text>
              </View>

              <View style={styles.featureRow}>
                <View style={styles.featureIconBox}>
                  <Ionicons name="checkmark" size={14} color={colors.primary} />
                </View>
                <Text style={styles.featureLabel} allowFontScaling>
                  {t("whatsapp.featureVoiceNotes")}
                </Text>
              </View>
            </View>
          </View>

          {/* Disconnect Action */}
          <TouchableOpacity
            style={styles.disconnectButton}
            onPress={() => setShowConfirmDisconnect(true)}
            accessibilityRole="button"
            accessibilityLabel={t("whatsapp.disconnectButton")}
            activeOpacity={0.8}
          >
            <Text style={styles.disconnectButtonText} allowFontScaling>
              {t("whatsapp.disconnectButton")}
            </Text>
          </TouchableOpacity>
        </View>

        {/* Nested Disconnect Confirmation Modal */}
        {showConfirmDisconnect ? (
          <View style={styles.confirmOverlay}>
            <View style={styles.confirmDialog} accessibilityRole="alert">
              <Text style={styles.confirmTitle} allowFontScaling>
                {t("whatsapp.disconnectConfirmTitle")}
              </Text>
              <Text style={styles.confirmMessage} allowFontScaling>
                {t("whatsapp.disconnectConfirmMessage")}
              </Text>

              <View style={styles.confirmActionsRow}>
                <TouchableOpacity
                  style={styles.cancelButton}
                  onPress={() => setShowConfirmDisconnect(false)}
                  disabled={disconnectMutation.isPending}
                  accessibilityRole="button"
                  accessibilityLabel={t("whatsapp.cancel")}
                >
                  <Text style={styles.cancelButtonText} allowFontScaling>
                    {t("whatsapp.cancel")}
                  </Text>
                </TouchableOpacity>

                <TouchableOpacity
                  style={[
                    styles.confirmDisconnectButton,
                    disconnectMutation.isPending && styles.buttonDisabled,
                  ]}
                  onPress={handleConfirmDisconnect}
                  disabled={disconnectMutation.isPending}
                  accessibilityRole="button"
                  accessibilityLabel={t("whatsapp.confirmDisconnect")}
                >
                  {disconnectMutation.isPending ? (
                    <ActivityIndicator color="#FFFFFF" size="small" />
                  ) : (
                    <Text style={styles.confirmDisconnectButtonText} allowFontScaling>
                      {t("whatsapp.confirmDisconnect")}
                    </Text>
                  )}
                </TouchableOpacity>
              </View>
            </View>
          </View>
        ) : null}
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: "rgba(10, 22, 18, 0.6)",
    justifyContent: "flex-end",
  },
  sheet: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: radii.lg,
    borderTopRightRadius: radii.lg,
    padding: spacing.lg,
    paddingBottom: spacing.xxl + 10,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    shadowColor: colors.primaryInk,
    shadowOffset: { width: 0, height: -6 },
    shadowOpacity: 0.1,
    shadowRadius: 20,
    elevation: 8,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.lg,
  },
  headerTitleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
  },
  headerIcon: {
    fontSize: 22,
  },
  title: {
    fontSize: typography.fontSize.headline,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
  },
  closeButton: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: "#F1F5F9",
    alignItems: "center",
    justifyContent: "center",
  },
  closeButtonText: {
    fontSize: 14,
    color: colors.textSecondary,
    fontWeight: typography.weight.bold,
  },
  detailsCard: {
    backgroundColor: "#F8FAFC",
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    padding: spacing.md,
    marginBottom: spacing.lg,
  },
  detailRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 4,
  },
  detailDivider: {
    height: 1,
    backgroundColor: "#E2E8F0",
    marginVertical: 6,
  },
  detailLabel: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textSecondary,
  },
  detailValue: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
  },
  statusBadge: {
    backgroundColor: "#DCF8C6",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radii.pill,
  },
  statusBadgeText: {
    color: "#075E54",
    fontSize: typography.fontSize.caption,
    fontWeight: typography.weight.bold,
  },
  featuresSection: {
    marginBottom: spacing.xl,
  },
  featuresSectionTitle: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.weight.bold,
    color: colors.textSecondary,
    letterSpacing: 0.8,
    marginBottom: spacing.sm,
  },
  featuresList: {
    gap: spacing.sm,
  },
  featureRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  featureIconBox: {
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: "#E6F4EA",
    alignItems: "center",
    justifyContent: "center",
  },
  featureCheck: {
    color: "#137333",
    fontSize: 12,
    fontWeight: typography.weight.bold,
  },
  featureLabel: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textPrimary,
  },
  disconnectButton: {
    borderWidth: 1,
    borderColor: "#FCA5A5",
    backgroundColor: "#FEF2F2",
    borderRadius: radii.pill,
    minHeight: touchTarget.min,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing.lg,
  },
  disconnectButtonText: {
    color: colors.critical,
    fontSize: typography.fontSize.bodySmall,
    fontWeight: typography.weight.bold,
  },
  confirmOverlay: {
    ...StyleSheet.absoluteFill,
    backgroundColor: "rgba(10, 22, 18, 0.7)",
    justifyContent: "center",
    alignItems: "center",
    padding: spacing.lg,
  },
  confirmDialog: {
    width: "100%",
    maxWidth: 340,
    backgroundColor: colors.surface,
    borderRadius: radii.lg,
    padding: spacing.xl,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    shadowColor: colors.primaryInk,
    shadowOffset: { width: 0, height: 12 },
    shadowOpacity: 0.2,
    shadowRadius: 24,
    elevation: 10,
  },
  confirmTitle: {
    fontSize: typography.fontSize.headline,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
    marginBottom: spacing.xs,
  },
  confirmMessage: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.textSecondary,
    lineHeight: 20,
    marginBottom: spacing.lg,
  },
  confirmActionsRow: {
    flexDirection: "row",
    justifyContent: "flex-end",
    gap: spacing.sm,
  },
  cancelButton: {
    paddingHorizontal: spacing.md,
    minHeight: touchTarget.min,
    justifyContent: "center",
    alignItems: "center",
  },
  cancelButtonText: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: typography.weight.semibold,
    color: colors.textSecondary,
  },
  confirmDisconnectButton: {
    backgroundColor: colors.critical,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.lg,
    minHeight: touchTarget.min,
    justifyContent: "center",
    alignItems: "center",
  },
  confirmDisconnectButtonText: {
    color: "#FFFFFF",
    fontSize: typography.fontSize.bodySmall,
    fontWeight: typography.weight.bold,
  },
  buttonDisabled: {
    opacity: 0.6,
  },
});
