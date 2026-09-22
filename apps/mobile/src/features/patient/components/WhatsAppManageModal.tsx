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
    ? new Date(identity.verified_at).toLocaleDateString([], {
        year: "numeric",
        month: "short",
        day: "numeric",
      })
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
              <View style={styles.waIconCircle}>
                <Ionicons name="logo-whatsapp" size={22} color="#25D366" />
              </View>
              <View>
                <Text style={styles.title} allowFontScaling>
                  {t("whatsapp.manageTitle")}
                </Text>
                <Text style={styles.subtitle} allowFontScaling>
                  Direct messaging & telemetry connection
                </Text>
              </View>
            </View>
            <TouchableOpacity
              onPress={handleClose}
              accessibilityRole="button"
              accessibilityLabel="Close"
              style={styles.closeButton}
              activeOpacity={0.7}
            >
              <Ionicons name="close" size={20} color="#0F172A" />
            </TouchableOpacity>
          </View>

          {/* Details Card */}
          <View style={styles.detailsCard}>
            <View style={styles.detailRow}>
              <Text style={styles.detailLabel} allowFontScaling>
                Status
              </Text>
              <View style={styles.statusBadge}>
                <Ionicons name="checkmark-circle" size={13} color="#059669" style={{ marginRight: 4 }} />
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
                  <Ionicons name="checkmark" size={13} color="#0D9488" />
                </View>
                <Text style={styles.featureLabel} allowFontScaling>
                  {t("whatsapp.featureHealthLogging")}
                </Text>
              </View>

              <View style={styles.featureRow}>
                <View style={styles.featureIconBox}>
                  <Ionicons name="checkmark" size={13} color="#0D9488" />
                </View>
                <Text style={styles.featureLabel} allowFontScaling>
                  {t("whatsapp.featureFoodLogging")}
                </Text>
              </View>

              <View style={styles.featureRow}>
                <View style={styles.featureIconBox}>
                  <Ionicons name="checkmark" size={13} color="#0D9488" />
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
            <Ionicons name="link-outline" size={17} color="#DC2626" style={{ marginRight: 6 }} />
            <Text style={styles.disconnectButtonText} allowFontScaling>
              {t("whatsapp.disconnectButton")}
            </Text>
          </TouchableOpacity>
        </View>

        {/* Nested Disconnect Confirmation Modal */}
        {showConfirmDisconnect ? (
          <View style={styles.confirmOverlay}>
            <View style={styles.confirmDialog} accessibilityRole="alert">
              <View style={styles.confirmIconCircle}>
                <Ionicons name="alert-circle-outline" size={26} color="#DC2626" />
              </View>

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
                  activeOpacity={0.7}
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
                  activeOpacity={0.85}
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
    backgroundColor: "rgba(15, 23, 42, 0.65)",
    justifyContent: "flex-end",
  },
  sheet: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: 28,
    borderTopRightRadius: 28,
    padding: spacing.lg,
    paddingBottom: spacing.xxl + 10,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: -8 },
    shadowOpacity: 0.12,
    shadowRadius: 24,
    elevation: 8,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.md + 4,
  },
  headerTitleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm + 2,
    flex: 1,
  },
  waIconCircle: {
    width: 42,
    height: 42,
    borderRadius: 14,
    backgroundColor: "#F0FDF4",
    borderWidth: 1,
    borderColor: "#DCFCE7",
    alignItems: "center",
    justifyContent: "center",
  },
  title: {
    fontSize: 18,
    fontWeight: "800",
    color: "#0F172A",
    letterSpacing: -0.3,
  },
  subtitle: {
    fontSize: 12,
    color: "#64748B",
    marginTop: 1,
  },
  closeButton: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: "#F8FAFC",
    borderWidth: 1,
    borderColor: "#E2E8F0",
    alignItems: "center",
    justifyContent: "center",
  },
  detailsCard: {
    backgroundColor: "#F8FAFC",
    borderRadius: 20,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    padding: spacing.md + 2,
    marginBottom: spacing.md + 4,
  },
  detailRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 4,
  },
  detailDivider: {
    height: 1,
    backgroundColor: "#EEF2F6",
    marginVertical: 6,
  },
  detailLabel: {
    fontSize: 13,
    color: "#64748B",
    fontWeight: "500",
  },
  detailValue: {
    fontSize: 13,
    fontWeight: "700",
    color: "#0F172A",
  },
  statusBadge: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#DCFCE7",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: "#BBF7D0",
  },
  statusBadgeText: {
    color: "#059669",
    fontSize: 11,
    fontWeight: "700",
  },
  featuresSection: {
    marginBottom: spacing.lg,
  },
  featuresSectionTitle: {
    fontSize: 11,
    fontWeight: "700",
    color: "#64748B",
    letterSpacing: 1.1,
    marginBottom: spacing.sm,
    marginLeft: 2,
  },
  featuresList: {
    gap: spacing.sm,
  },
  featureRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  featureIconBox: {
    width: 22,
    height: 22,
    borderRadius: 8,
    backgroundColor: "#F0FDFA",
    borderWidth: 1,
    borderColor: "#CCFBF1",
    alignItems: "center",
    justifyContent: "center",
  },
  featureLabel: {
    fontSize: 13,
    color: "#0F172A",
    fontWeight: "500",
  },
  disconnectButton: {
    flexDirection: "row",
    borderWidth: 1,
    borderColor: "#FECACA",
    backgroundColor: "#FEF2F2",
    borderRadius: radii.pill,
    minHeight: 48,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing.lg,
  },
  disconnectButtonText: {
    color: "#DC2626",
    fontSize: 14,
    fontWeight: "700",
  },
  confirmOverlay: {
    ...StyleSheet.absoluteFill,
    backgroundColor: "rgba(15, 23, 42, 0.65)",
    justifyContent: "center",
    alignItems: "center",
    padding: spacing.lg,
  },
  confirmDialog: {
    width: "100%",
    maxWidth: 340,
    backgroundColor: colors.surface,
    borderRadius: 24,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    alignItems: "center",
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 12 },
    shadowOpacity: 0.15,
    shadowRadius: 24,
    elevation: 10,
  },
  confirmIconCircle: {
    width: 54,
    height: 54,
    borderRadius: 27,
    backgroundColor: "#FEE2E2",
    borderWidth: 1,
    borderColor: "#FECACA",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.sm + 2,
  },
  confirmTitle: {
    fontSize: 17,
    fontWeight: "800",
    color: "#0F172A",
    marginBottom: spacing.xs,
    textAlign: "center",
    letterSpacing: -0.2,
  },
  confirmMessage: {
    fontSize: 13,
    color: "#64748B",
    lineHeight: 19,
    marginBottom: spacing.md + 4,
    textAlign: "center",
  },
  confirmActionsRow: {
    flexDirection: "row",
    gap: spacing.sm,
    width: "100%",
  },
  cancelButton: {
    flex: 1,
    minHeight: 46,
    borderRadius: radii.pill,
    backgroundColor: "#F1F5F9",
    borderWidth: 1,
    borderColor: "#E2E8F0",
    justifyContent: "center",
    alignItems: "center",
  },
  cancelButtonText: {
    fontSize: 14,
    fontWeight: "600",
    color: "#475569",
  },
  confirmDisconnectButton: {
    flex: 1,
    backgroundColor: "#DC2626",
    borderRadius: radii.pill,
    minHeight: 46,
    justifyContent: "center",
    alignItems: "center",
    shadowColor: "#DC2626",
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.25,
    shadowRadius: 6,
    elevation: 2,
  },
  confirmDisconnectButtonText: {
    color: "#FFFFFF",
    fontSize: 14,
    fontWeight: "700",
  },
  buttonDisabled: {
    opacity: 0.6,
  },
});
